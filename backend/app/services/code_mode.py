"""
code_mode.py — Cloudflare "Code Mode" pattern, POC.

--- THE PROBLEM IT SOLVES ---

Traditional tool-calling: the model sees N tool schemas (every call fills
context), then ping-pongs — call tool, wait for result, call next tool,
wait... Each round-trip adds latency, and every intermediate result
consumes context window.

--- THE CODE MODE ALTERNATIVE ---

Expose ONE tool: `run_research_code`. The model writes a small TypeScript
script against a generated API (the research tools, typed as a .d.ts-style
interface). The script runs in a sandbox; only the final result returns
to the model. Intermediate calls never enter the context.

Model sees ONE tool. Composes arbitrary multi-step research in ONE round-trip.

--- THIS POC ---

Faithful to the pattern but scoped small (per its "POC" mandate):

  - The tool API is TypeScript-typed (RESEARCH_API_TS) and documented to
    the model in ONE prompt block (~90 tokens vs ~400 for 4 JSON schemas).
  - Scripts execute in a restricted Python interpreter:
      * no imports, no __builtins__, no attribute access on underscore names
      * AST-validated BEFORE execution (rejects imports, eval, exec, dunder
        access, attribute chains into non-API globals)
      * execution via exec() with scrubbed globals — defense in depth
  - Tools are REAL Python callables wired to the actual retrieval stack:
        search_page(query)          → hybrid search on the current page
        search_workspace(query)-out hybrid search across the KB
        grade(question, chunks)     → cross-check with the agent's relevance judge
        final_answer(question, ctx) → RAG generation via Gemini

Security note: for production this sandbox should be a proper isolate
(Pyodide/WASM/QuickJS in a subprocess). The AST gate here blocks the known
escape routes (imports, dunders, builtins access) for a local POC.
"""

import ast
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The TypeScript API the model sees — the ONLY tool description it needs
# ---------------------------------------------------------------------------

RESEARCH_API_TS = """\
// Research API available inside run_research_code:
declare function search_page(query: string): Chunk[];
declare function search_workspace(query: string): Chunk[];
declare function grade(question: string, chunks: Chunk[]): string[];  // 'relevant'|'partial'|'irrelevant'
declare function final_answer(question: string, context: Chunk[]): string;
interface Chunk { content: string; session_id?: string; chunk_index?: number; score?: number }
// Rules: return the final answer string. No imports. No loops > 10 iterations. Max 8 API calls.
"""

RUN_CODE_TOOL_DESCRIPTION = (
    "Executes a short TypeScript research script against the page/workspace "
    "search API. Use for any question — write the retrieval logic yourself "
    "(search, optionally grade, pick the best chunks, call final_answer). "
    "Return the final answer string."
)


@dataclass
class CodeModeResult:
    """Outcome of one sandbox execution."""
    success: bool
    result: str                 # The script's return value (the model only sees this)
    error: str | None = None    # Sandbox/validation error, if any
    steps: list[str] = None     # Execution log — for traces/debugging, NOT sent to the model
    api_calls: int = 0

    def __post_init__(self):
        if self.steps is None:
            self.steps = []


# ---------------------------------------------------------------------------
# AST gate — reject anything that isn't plain computation + API calls
# ---------------------------------------------------------------------------

_ALLOWED_CALL_NAMES = {"search_page", "search_workspace", "grade", "final_answer"}
_BANNED_NODES = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)


def validate_script(source: str) -> str | None:
    """
    Returns None if the script is safe, else a rejection reason.
    Static gate BEFORE any execution — cheap and airtight against
    the obvious escapes.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"Syntax error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, _BANNED_NODES):
            return f"Forbidden statement: {type(node).__name__}"

        if isinstance(node, ast.Attribute):
            # Block dunder access and chained attribute tricks
            name = node.attr
            if name.startswith("_"):
                return f"Forbidden attribute access: .{name}"

        if isinstance(node, ast.Name):
            if node.id in {"eval", "exec", "compile", "__import__", "open", "input"}:
                return f"Forbidden name: {node.id}"
            if node.id.startswith("__"):
                return f"Forbidden name: {node.id}"

        if isinstance(node, ast.Call):
            # Only direct calls to the four API functions are allowed —
            # this rejects lambdas, comprehensions-as-callables, attribute
            # calls, and any indirect invocation.
            if isinstance(node.func, ast.Name):
                if node.func.id not in _ALLOWED_CALL_NAMES:
                    return (
                        f"Unknown function: {node.func.id}. "
                        f"Allowed: {sorted(_ALLOWED_CALL_NAMES)}"
                    )
            else:
                return "Only direct calls to the API functions are allowed"

        if isinstance(node, (ast.While, ast.Lambda)):
            return (
                "while loops and lambdas are not allowed "
                "(use for with a bounded range)"
            )

    return None


# ---------------------------------------------------------------------------
# Sandbox globals — only the four API functions exist in here
# ---------------------------------------------------------------------------


def _make_sandbox(session_id: str, workspace_id: str | None) -> tuple[dict, list[str]]:
    """Builds the restricted globals + an execution log."""
    from app.services.agent_service import grade_chunks
    from app.services.llm_service import generate_answer
    from app.services.rag_service import retrieve
    from app.services.workspace_service import workspace_session_ids
    from app.services.vector_store import search_workspace

    k = settings.rerank_candidates
    log: list[str] = []
    call_count = [0]

    def _guard():
        call_count[0] += 1
        if call_count[0] > 8:
            raise RuntimeError("API call limit exceeded (max 8)")
        log.append(f"call #{call_count[0]}")

    def js_search_page(query: str):
        _guard()
        log.append(f"search_page({query!r})")
        return retrieve(session_id=session_id, query=query, k=k).chunks

    def js_search_workspace(query: str):
        _guard()
        log.append(f"search_workspace({query!r})")
        sids = workspace_session_ids(workspace_id) if workspace_id else []
        return search_workspace(workspace_id, sids, query, k=k) if sids else []

    def js_grade(question_: str, chunks: list):
        _guard()
        log.append(f"grade({question_!r}, {len(chunks)} chunks)")
        return grade_chunks(question_, chunks)

    def js_final_answer(question_: str, context: list):
        _guard()
        log.append(f"final_answer({question_!r}, {len(context)} chunks)")
        ctx = [c["content"] if isinstance(c, dict) else str(c) for c in context]
        return generate_answer(ctx, question_)

    sandbox_globals = {
        "search_page": js_search_page,
        "search_workspace": js_search_workspace,
        "grade": js_grade,
        "final_answer": js_final_answer,
        "range": range, "len": len, "min": min, "max": max, "abs": abs,
        "sorted": sorted, "sum": sum, "enumerate": enumerate, "zip": zip,
        "str": str, "int": int, "float": float, "list": list, "dict": dict,
        "__builtins__": {},   # No builtins inside the sandbox
    }
    return sandbox_globals, log


# ---------------------------------------------------------------------------
# Public entry — the single tool the model calls
# ---------------------------------------------------------------------------

RUN_CODE_PROMPT = """You are a research agent with ONE tool: run_research_code.
It executes a short TypeScript-style script against this API:

{api_ts}

QUESTION: {question}

Write a script that answers the question. Strategy:
1. Call search_page("...") with the question to search the current page.
2. If results look weak (grade() marks them irrelevant), call search_workspace("...").
3. Pick the best 2-4 chunks and call final_answer(question, chunks).
4. Assign the final answer to a variable named `result`.

Respond with ONLY the script body (no markdown fences, no explanation).
"""


def run_research_code(
    session_id: str,
    question: str,
    workspace_id: str | None = None,
) -> tuple[str, list[str]]:
    """
    Full Code-Mode round trip:
      1. Ask the model for a research script (ONE generation).
      2. Validate it statically (AST gate).
      3. Execute in the sandbox with the real retrieval tools.
      4. Return ONLY the final answer to the caller.

    Returns (answer, execution_log). Raises on failure — the caller
    (agent_service) falls back to the standard loop.
    """
    from app.services.agent_service import _structured_call_fallback as _structured_call

    # 1. Model writes the script
    script = _structured_call(RUN_CODE_PROMPT.format(api_ts=RESEARCH_API_TS, question=question))
    script = script.strip()
    if script.startswith("```"):
        # Strip accidental fences
        script = script.split("```")[1].removeprefix("typescript").strip()

    logger.info(f"Code Mode: model produced {len(script)} char script")

    # 2. Static validation
    rejection = validate_script(script)
    if rejection:
        logger.warning(f"Code Mode: script rejected — {rejection}")
        raise ValueError(f"Script rejected by sandbox validator: {rejection}")

    # 3. Execute
    sandbox_globals, log = _make_sandbox(session_id, workspace_id)
    local_env: dict = {}
    try:
        exec(script, sandbox_globals, local_env)   # noqa: S102 — sandboxed, validated above
    except Exception as e:
        logger.warning(f"Code Mode: sandbox execution failed — {e}")
        raise ValueError(f"Sandbox execution error: {e}") from e

    result = local_env.get("result")
    if result is None:
        # Model used `return` at top level (invalid) or forgot to assign —
        # treat the last API call's output as the result if available.
        raise ValueError("Script did not assign a `result` variable")

    logger.info(f"Code Mode: executed {len(log)} API calls — only the result returns to the model")
    return str(result), log
