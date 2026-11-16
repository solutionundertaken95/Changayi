"""
chat_service.py — Orchestrates the full RAG chat pipeline.

This is the "conductor" for Phase 3. It connects:
  - rag_service   (retrieval — Phase 2)
  - llm_service   (Gemini answer generation — Phase 3)

--- FULL DATA FLOW ---

  User asks: "What is the main argument of this article?"
       │
       ▼
  chat_service.chat()
       │
       ├─ 1. rag_service.retrieve()
       │       → embeds the question
       │       → searches ChromaDB
       │       → returns top-4 most relevant chunks
       │
       ├─ 2. llm_service.generate_answer()
       │       → builds RAG prompt (system rules + context + question)
       │       → sends to Gemini API
       │       → returns answer text
       │
       └─ 3. Returns ChatResult
               → answer (the generated text)
               → sources (the chunks used — so we can show them in the UI)

--- WHY RETURN SOURCES? ---

  Returning the source chunks alongside the answer makes the RAG
  process transparent to the user. They can see WHICH parts of the
  page informed the answer. This is a key feature of a trustworthy
  AI system — it's not a black box, it shows its work.

  In the React UI (Phase 5), sources will appear as collapsible
  cards below the answer.
"""

import logging
from dataclasses import dataclass

from app.services import rag_service
from app.services import llm_service
from app.services import workspace_service
from app.services.vector_store import search_workspace

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """The complete result of one chat turn."""
    session_id: str
    question: str
    answer: str
    sources: list[dict]   # Each: { content, chunk_index, session_id? }
    workspace_id: str | None = None


def chat(session_id: str, question: str, k: int = 4, workspace_id: str | None = None) -> ChatResult:
    """
    Runs the full RAG pipeline for a single user question.

    Two retrieval scopes:
      - workspace_id is None (default): search only this session's page.
      - workspace_id is set: FAN OUT across every page registered in the
        workspace — hybrid search runs per page collection, merged
        candidates are deduplicated, and the cross-encoder reranks the
        combined pool so chunks from different tabs compete fairly.

    Args:
        session_id:   Must match the session_id used when the page was indexed.
        question:     The user's question from the chat input.
        k:            Number of chunks to retrieve (default 4).
        workspace_id: Optional workspace to search across multiple tabs.

    Returns:
        ChatResult with the answer and the source chunks used.

    Raises:
        ValueError: If the session/workspace has no indexed content
        Exception:  If retrieval or Gemini call fails
    """
    scope = f"workspace='{workspace_id}'" if workspace_id else f"session='{session_id}'"
    logger.info(f"Chat request | {scope} | question='{question[:60]}'")

    # ── Step 1: Retrieve relevant chunks ──────────────────────────────
    logger.info("Step 1/2: Retrieving relevant chunks...")

    if workspace_id:
        session_ids = workspace_service.workspace_session_ids(workspace_id)
        if not session_ids:
            logger.warning(f"Workspace '{workspace_id}' has no pages or does not exist")
            return ChatResult(
                session_id=session_id,
                question=question,
                answer=(
                    "This workspace has no indexed pages yet. "
                    "Open a page, index it, and add it to the workspace first."
                ),
                sources=[],
                workspace_id=workspace_id,
            )

        chunks = search_workspace(
            workspace_id=workspace_id,
            session_ids=session_ids,
            query=question,
            k=k,
        )
    else:
        retrieval = rag_service.retrieve(session_id=session_id, query=question, k=k)
        chunks = retrieval.chunks

    if not retrieval.chunks:
        # This means the page hasn't been indexed yet, or the session_id is wrong
        logger.warning(f"No chunks found for session '{session_id}'")
        return ChatResult(
            session_id=session_id,
            question=question,
            answer=(
                "It looks like this page hasn't been analyzed yet. "
                "Please wait a moment while I read the page, then try again."
            ),
            sources=[],
            workspace_id=workspace_id,
        )

    # Extract just the text content for the prompt
    chunk_texts = [c["content"] for c in chunks]

    logger.info(f"  → {len(chunk_texts)} chunks retrieved")

    # ── Step 2: Generate answer with Gemini ───────────────────────────
    logger.info("Step 2/2: Generating answer with Gemini...")

    answer = llm_service.generate_answer(
        context_chunks=chunk_texts,
        question=question,
    )

    logger.info(f"  → Answer generated ({len(answer)} chars)")

    return ChatResult(
        session_id=session_id,
        question=question,
        answer=answer,
        sources=chunks,  # Full chunk dicts (content, chunk_index, session_id?)
        workspace_id=workspace_id,
    )
