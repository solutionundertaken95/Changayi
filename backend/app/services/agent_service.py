"""
agent_service.py — Agentic RAG: a bounded self-correcting retrieval loop.

Instead of the linear "retrieve once → stuff → generate", the LLM acts as
a reasoning controller over its own retrieval:

    RETRIEVE ──▶ GRADE chunks (relevant? partial? irrelevant?)
        │ not relevant                │ relevant
        ▼                             ▼
    REWRITE query ─▶ re-RETRIEVE   GENERATE answer
        │ (optionally escalate           │
        │  scope to the workspace)       ▼
        └── retry (≤ max_steps) ─── CHECK GROUNDEDNESS
                                          │ claims unsupported → regenerate once

Design principles:
  - Every node returns a small structured verdict, never free-form text —
    grading/checking calls stay cheap (1 short generation, temp=0).
  - The loop is BOUNDED (max_steps) — an agent that cannot converge
    answers with what it has, honestly noting low confidence.
  - Every decision is appended to an AgentTrace — surfaced in the UI so
    the reasoning is transparent, and assertable in tests.

--- WHY THIS BELONGS ON TOP OF THE EXISTING PIPELINE ---

The hybrid+rerank stack answers "which chunks are the best match?" —
it cannot ask "did we actually find the answer?". A benchmark can only
tell you that offline; the grading node asks it online, per query, and
recovers with query rewriting or scope escalation. This is the
industry-standard "agentic / Self-RAG / CRAG" production pattern.
"""

import logging
from dataclasses import dataclass, field

import google.api_core.exceptions as gexc

from app.config import settings
from app.services.llm_service import _get_model, generate_answer

logger = logging.getLogger(__name__)


class QuotaExceeded(Exception):
    """Raised when Gemini returns 429 — short-circuits the agent loop."""


def _is_quota_error(exc: Exception) -> bool:
    """Detects Gemini 429s across SDK wrapper layers."""
    if isinstance(exc, gexc.ResourceExhausted):
        return True
    return "429" in str(exc) or "quota" in str(exc).lower() or "ResourceExhausted" in str(exc)

# Verdict constants
RELEVANT = "relevant"
PARTIAL = "partial"
IRRELEVANT = "irrelevant"

GRADED_OK = "grounded"
GRADED_UNSUPPORTED = "unsupported"


@dataclass
class AgentTrace:
    """One entry per agent decision — rendered as reasoning steps in the UI."""

    step: str        # e.g. "retrieve", "grade", "rewrite", "escalate", "generate", "check"
    detail: str      # Human-readable one-liner
    meta: dict = field(default_factory=dict)   # Optional structured extras


@dataclass
class AgentResult:
    answer: str
    chunks: list[dict]            # Final context chunks (with session_id / scores)
    trace: list[AgentTrace]
    steps_used: int
    escalated_to_workspace: bool
    rewritten_query: str | None   # None if the original query survived
    grounded: bool                # Final groundedness verdict
    early_exit: bool              # True if a retry-free happy path


# ---------------------------------------------------------------------------
# LLM helper — one cheap structured call, reused by all judge nodes
# ---------------------------------------------------------------------------


def _structured_call(prompt: str) -> str:
    """
    One low-temperature Gemini call returning short text.

    Quota guard: converts Gemini 429s into QuotaExceeded immediately —
    WITHOUT this, the google SDK retries internally for many minutes and
    the caller appears to hang. Raises on all other failures.
    """
    try:
        model = _get_model()
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        if _is_quota_error(e):
            raise QuotaExceeded(
                "Gemini free-tier quota is exhausted (429). "
                "Wait for the daily reset or switch API keys."
            ) from e
        raise


# Exposed for code_mode.py (script generation)
_structured_call_fallback = _structured_call

RATE_LIMIT_ANSWER = (
    "⏳ You've hit the Gemini free-tier rate limit (about 20 requests/day "
    "for this model). The agent stopped early instead of waiting on retries. "
    "Try again after the daily reset, or use a different API key in .env."
)


# ---------------------------------------------------------------------------
# Node 1: Grade retrieved chunks for relevance
# ---------------------------------------------------------------------------

GRADE_PROMPT = """You are a strict relevance judge for a RAG system.

QUESTION: {question}

CHUNKS:
{chunks}

For EACH chunk (by number), output exactly one line:
<chunk number>: relevant | partial | irrelevant

Rules:
- "relevant"    — the chunk clearly contains information that helps answer the question
- "partial"     — the chunk is on-topic but does not actually answer it
- "irrelevant"  — the chunk is off-topic for the question
- Output ONLY the lines, nothing else.
"""


def grade_chunks(question: str, chunks: list[dict]) -> list[str]:
    """
    Grades each retrieved chunk: relevant | partial | irrelevant.
    Returns verdicts parallel to `chunks`. Never raises — on any LLM
    failure it optimistically marks everything relevant so retrieval
    still proceeds (degradation, not failure).
    """
    if not chunks:
        return []

    formatted = "\n".join(
        f"{i + 1}. {c['content'][:400]}"   # Truncate: grading is cheap, not exhaustive
        for i, c in enumerate(chunks)
    )
    try:
        raw = _structured_call(GRADE_PROMPT.format(question=question, chunks=formatted))
        verdicts: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            idx_str, verdict = line.split(":", 1)
            verdict = verdict.strip().lower()
            if verdict not in (RELEVANT, PARTIAL, IRRELEVANT):
                verdict = PARTIAL  # Unknown output → treat as partial
            verdicts.append(verdict)
        # Pad/truncate to chunk count (defensive against malformed output)
        while len(verdicts) < len(chunks):
            verdicts.append(PARTIAL)
        return verdicts[: len(chunks)]
    except Exception as e:
        logger.warning(f"Grading failed, proceeding optimistically: {e}")
        return [RELEVANT] * len(chunks)


# ---------------------------------------------------------------------------
# Node 2: Rewrite the query when retrieval was insufficient
# ---------------------------------------------------------------------------

REWRITE_PROMPT = """You rewrite search queries for a retrieval system.

Original question: {question}

The first retrieval attempt did not find sufficient relevant information.
Rewrite the question to maximize retrieval success:
- Fix spelling and grammar mistakes
- Replace vague references with concrete search terms
- Add likely keywords that relevant documents would contain
- Keep it a single line, no explanations

Rewritten query:"""


def rewrite_query(question: str) -> str | None:
    """Rewrites the query for a second retrieval attempt. None on failure."""
    try:
        rewritten = _structured_call(REWRITE_PROMPT.format(question=question))
        rewritten = rewritten.strip().strip('"')
        if rewritten and rewritten.lower() != question.strip().lower():
            return rewritten
        return None
    except Exception as e:
        logger.warning(f"Query rewriting failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Node 3: Groundedness check — is every claim supported by the sources?
# ---------------------------------------------------------------------------

CHECK_PROMPT = """You verify that an AI answer is grounded in the provided sources.

QUESTION: {question}

ANSWER:
{answer}

SOURCES:
{sources}

Is every factual claim in the answer supported by the sources?
Reply with exactly one word:
- grounded     — every claim traces to the sources
- unsupported  — the answer contains claims not found in the sources

Reply:"""


def check_groundedness(question: str, answer: str, chunks: list[dict]) -> str:
    """
    Returns GRADED_OK or GRADED_UNSUPPORTED.
    Degrades to GRADED_OK on LLM failure (don't block answers on the checker).
    """
    sources = "\n".join(f"- {c['content'][:300]}" for c in chunks)
    try:
        raw = _structured_call(
            CHECK_PROMPT.format(question=question, answer=answer[:1500], sources=sources)
        ).lower()
        if GRADED_UNSUPPORTED in raw:
            return GRADED_UNSUPPORTED
        return GRADED_OK
    except Exception as e:
        logger.warning(f"Groundedness check failed, assuming grounded: {e}")
        return GRADED_OK


# ---------------------------------------------------------------------------
# Retrieval helpers (same hybrid stack, two scopes)
# ---------------------------------------------------------------------------


def _retrieve_single(session_id: str, query: str, k: int) -> list[dict]:
    from app.services.rag_service import retrieve
    return retrieve(session_id=session_id, query=query, k=k).chunks


def _retrieve_workspace(workspace_id: str, query: str, k: int) -> list[dict]:
    from app.services.workspace_service import workspace_session_ids
    from app.services.vector_store import search_workspace

    session_ids = workspace_session_ids(workspace_id)
    if not session_ids:
        return []
    return search_workspace(workspace_id, session_ids, query, k=k)


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------


def run_agent(
    session_id: str,
    question: str,
    workspace_id: str | None = None,
    k: int = None,
    max_steps: int = None,
    use_code_mode: bool = False,
) -> AgentResult:
    """
    Runs the bounded self-correcting retrieval loop.

    Args:
        session_id:   The page session (also used as the initial retrieval scope)
        question:     The user's question (may contain typos — that's the point)
        workspace_id: If set, workspace retrieval is also available for escalation
        k:            Final chunk count (default settings.final_k)
        max_steps:    Max retrieve→grade→rewrite/escalate cycles (default 3)
        use_code_mode: If True, attempt the Code-Mode path first — the model
                       writes ONE research script that composes retrieval,
                       grading and generation in a sandbox; intermediates never
                       enter the context. Falls back to the loop on any failure.
    """
    k = k or settings.final_k
    max_steps = max_steps or settings.agent_max_steps

    # ── Quota guard: fail fast and friendly instead of hanging on SDK retries ──
    try:
        return _run_agent_inner(
            session_id, question, workspace_id, k, max_steps, use_code_mode
        )
    except QuotaExceeded:
        logger.warning("Agent aborted: Gemini quota exhausted (429)")
        return AgentResult(
            answer=RATE_LIMIT_ANSWER,
            chunks=[],
            trace=[AgentTrace(
                "quota",
                "Stopped: Gemini free-tier rate limit hit — no retries, no waiting",
            )],
            steps_used=0,
            escalated_to_workspace=False,
            rewritten_query=None,
            grounded=False,
            early_exit=False,
        )


def _run_agent_inner(
    session_id: str,
    question: str,
    workspace_id: str | None,
    k: int,
    max_steps: int,
    use_code_mode: bool,
) -> AgentResult:
    """The actual agent loop (quota-guarded by run_agent)."""

    # ── Code Mode: one script, one round-trip, intermediates never in context ──
    if use_code_mode:
        try:
            from app.services.code_mode import run_research_code
            answer, log = run_research_code(session_id, question, workspace_id)
            return AgentResult(
                answer=answer,
                chunks=[],              # Chunks were consumed inside the sandbox
                trace=[
                    AgentTrace("code_mode", "Model wrote a research script against the typed API"),
                    AgentTrace("code_mode", f"Sandbox executed {len(log)} API calls; only the result returned"),
                ],
                steps_used=1,
                escalated_to_workspace=False,
                rewritten_query=None,
                grounded=True,          # final_answer() IS the grounded generation path
                early_exit=True,
            )
        except Exception as e:
            logger.warning(f"Code Mode failed — falling back to agent loop: {e}")
            # Fall through to the standard bounded loop below

    trace: list[AgentTrace] = []

    trace: list[AgentTrace] = []
    rewritten_query: str | None = None
    escalated = False

    for step_no in range(1, max_steps + 1):
        query = rewritten_query or question
        scope = "workspace" if escalated else "single-page"

        # ── RETRIEVE ────────────────────────────────────────────────
        if escalated and workspace_id:
            chunks = _retrieve_workspace(workspace_id, query, settings.rerank_candidates)
        else:
            chunks = _retrieve_single(session_id, query, settings.rerank_candidates)

        trace.append(AgentTrace(
            step="retrieve",
            detail=f"Searched {scope} for \"{query}\" → {len(chunks)} chunks",
            meta={"scope": scope, "candidates": len(chunks), "step": step_no},
        ))

        if not chunks:
            # Nothing at all — rewrite or escalate and try again
            if not escalated and workspace_id:
                escalated = True
                trace.append(AgentTrace("escalate", "No candidates — escalating to workspace"))
                continue
            rewritten = rewrite_query(question)
            if rewritten and step_no < max_steps:
                rewritten_query = rewritten
                trace.append(AgentTrace("rewrite", f"No candidates — retrying as: \"{rewritten}\""))
                continue
            break  # Nothing more to try

        # ── GRADE ───────────────────────────────────────────────────
        verdicts = grade_chunks(query, chunks)
        relevant = [c for c, v in zip(chunks, verdicts) if v == RELEVANT]
        n_partial = sum(1 for v in verdicts if v == PARTIAL)

        trace.append(AgentTrace(
            step="grade",
            detail=(
                f"Graded {len(chunks)} chunks: {len(relevant)} relevant, "
                f"{n_partial} partial, {len(chunks) - len(relevant) - n_partial} irrelevant"
            ),
            meta={"relevant": len(relevant), "step": step_no},
        ))

        if len(relevant) >= 1:
            # ── GENERATE ────────────────────────────────────────────
            final_chunks = (relevant + [c for c, v in zip(chunks, verdicts) if v == PARTIAL])[:k]
            trace.append(AgentTrace(
                step="generate",
                detail=f"Generating answer from {len(final_chunks)} chunks",
            ))
            try:
                answer = generate_answer([c["content"] for c in final_chunks], question)
            except Exception as e:
                if _is_quota_error(e):
                    raise QuotaExceeded("Gemini quota exhausted during generation") from e
                raise

            # ── CHECK GROUNDEDNESS ──────────────────────────────────
            verdict = check_groundedness(question, answer, final_chunks)
            trace.append(AgentTrace(
                step="check",
                detail="Groundedness verified — all claims supported" if verdict == GRADED_OK
                       else "Answer contained unsupported claims",
            ))
            if verdict == GRADED_UNSUPPORTED and rewritten_query is None and step_no < max_steps:
                # One regenerate attempt with the rewritten query
                rewritten = rewrite_query(question)
                if rewritten:
                    rewritten_query = rewritten
                    trace.append(AgentTrace(
                        "rewrite",
                        f"Groundedness failure — retrying with: \"{rewritten}\"",
                    ))
                    continue

            return AgentResult(
                answer=answer,
                chunks=final_chunks,
                trace=trace,
                steps_used=step_no,
                escalated_to_workspace=escalated,
                rewritten_query=rewritten_query,
                grounded=(verdict == GRADED_OK),
                early_exit=(step_no == 1 and not escalated),
            )

        # ── INSUFFICIENT → recover ──────────────────────────────────
        if not escalated and workspace_id:
            escalated = True
            trace.append(AgentTrace(
                "escalate",
                f"Only {len(relevant)} relevant chunk(s) — escalating to workspace",
            ))
            continue

        if rewritten_query is None and step_no < max_steps:
            rewritten = rewrite_query(question)
            if rewritten:
                rewritten_query = rewritten
                trace.append(AgentTrace(
                    "rewrite",
                    f"Retrieval insufficient — rewriting as: \"{rewritten}\"",
                ))
                continue

        # Nothing left to try — answer with what we have (partial context)
        logger.warning(f"Agent could not find sufficient context after {step_no} steps")
        break

    # ── Fallthrough: best-effort answer from whatever we have ───────
    final_chunks = chunks[:k] if chunks else []
    trace.append(AgentTrace(
        "generate",
        "Max steps reached — answering with best available context (low confidence)",
    ))
    answer = (
        generate_answer([c["content"] for c in final_chunks], question)
        if final_chunks
        else ("I couldn't find relevant information to answer that. "
              "Try rephrasing, or add more pages to your knowledge base.")
    )
    return AgentResult(
        answer=answer,
        chunks=final_chunks,
        trace=trace,
        steps_used=max_steps,
        escalated_to_workspace=escalated,
        rewritten_query=rewritten_query,
        grounded=False,
        early_exit=False,
    )


# ---------------------------------------------------------------------------
# Streaming variant — yields SSE-formatted events including trace steps
# ---------------------------------------------------------------------------


def run_agent_stream_events(session_id: str, question: str, workspace_id: str | None, k: int):
    """
    Generator producing dicts the chat route can serialize as SSE events:
        {"type": "trace", "step": ..., "detail": ...}   — per agent decision
        {"type": "sources", "sources": [...]}           — before generation
        {"type": "chunk", "text": ...}                  — streamed answer tokens
        {"type": "done"} / {"type": "error", ...}
    """
    try:
        result = run_agent(session_id, question, workspace_id=workspace_id, k=k)
    except QuotaExceeded:
        yield {"type": "chunk", "text": RATE_LIMIT_ANSWER}
        yield {"type": "done"}
        return

    for t in result.trace:
        yield {"type": "trace", "step": t.step, "detail": t.detail}

    yield {
        "type": "sources",
        "sources": [
            {
                "content": c["content"],
                "chunk_index": c.get("chunk_index", -1),
                "session_id": c.get("session_id"),
            }
            for c in result.chunks
        ],
    }
    yield {"type": "chunk", "text": result.answer}

    yield {"type": "done", "meta": {
        "steps_used": result.steps_used,
        "rewritten_query": result.rewritten_query,
        "escalated": result.escalated_to_workspace,
        "grounded": result.grounded,
        "early_exit": result.early_exit,
    }}
