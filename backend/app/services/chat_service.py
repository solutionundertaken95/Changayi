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

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """The complete result of one chat turn."""
    session_id: str
    question: str
    answer: str
    sources: list[dict]   # Each: { content: str, chunk_index: int }


def chat(session_id: str, question: str, k: int = 4) -> ChatResult:
    """
    Runs the full RAG pipeline for a single user question.

    Args:
        session_id: Must match the session_id used when the page was indexed.
                    This tells ChromaDB which page's chunks to search.
        question:   The user's question from the chat input.
        k:          Number of chunks to retrieve (default 4).
                    More chunks = more context, but also longer prompt.

    Returns:
        ChatResult with the answer and the source chunks used.

    Raises:
        ValueError: If the session has no indexed content (page not indexed yet)
        Exception:  If retrieval or Gemini call fails
    """
    logger.info(f"Chat request | session='{session_id}' | question='{question[:60]}'")

    # ── Step 1: Retrieve relevant chunks from ChromaDB ────────────────────
    logger.info("Step 1/2: Retrieving relevant chunks...")

    retrieval = rag_service.retrieve(
        session_id=session_id,
        query=question,
        k=k,
    )

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
        )

    # Extract just the text content for the prompt
    chunk_texts = [c["content"] for c in retrieval.chunks]

    logger.info(f"  → {len(chunk_texts)} chunks retrieved")

    # ── Step 2: Generate answer with Gemini ───────────────────────────────
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
        sources=retrieval.chunks,  # Pass the full chunk dicts (content + chunk_index)
    )
