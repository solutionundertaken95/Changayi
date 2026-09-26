"""
rag_service.py — Orchestrates the full RAG indexing and retrieval pipeline.

This file is the coordinator. It doesn't know about:
  - FastAPI (HTTP requests/responses)
  - Gemini (LLM — that's added in Phase 3)

It only knows about:
  - Cleaning text
  - Chunking text
  - Storing chunks in ChromaDB
  - Searching ChromaDB

This separation means in Phase 3, we can add Gemini without
touching any of the lower-level services.

--- THE FULL PIPELINE (what happens when a user opens the chatbot) ---

  Chrome Extension
       │
       │  POST /api/page/index
       │  { session_id, url, title, content }
       ▼
  rag_service.index_page()
       │
       ├──▶ cleaner.clean_text()
       │        Remove noise, normalize unicode, collapse whitespace
       │
       ├──▶ chunker.chunk_text()
       │        Split into ~500 char overlapping chunks
       │
       ├──▶ vector_store.store_chunks()
       │        Embed each chunk → store in ChromaDB
       │
       └──▶ Return stats (chunks created, etc.)

--- RETRIEVAL FLOW (when user asks a question) ---

  User question
       │
  rag_service.retrieve()
       │
       └──▶ vector_store.search_chunks()
                Embed question → cosine similarity → top-k chunks
"""

import logging
from dataclasses import dataclass

from app.services.cleaner import clean_text, get_text_stats
from app.services.chunker import chunk_text, get_chunk_stats
from app.services.vector_store import store_chunks, search_chunks

logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    """Returned after successfully indexing a page."""
    session_id: str
    url: str
    original_length: int     # Characters before cleaning
    cleaned_length: int      # Characters after cleaning
    chunks_created: int
    chunk_stats: dict


@dataclass
class RetrievalResult:
    """Returned after a similarity search."""
    session_id: str
    query: str
    chunks: list[dict]       # Each dict: { content, chunk_index }


def index_page(
    session_id: str,
    url: str,
    title: str,
    content: str,
) -> IndexResult:
    """
    Full indexing pipeline: clean → chunk → embed → store.

    Called when the Chrome extension sends a new page's content.
    Any existing data for this session_id is replaced.

    Args:
        session_id: Unique ID for the browser tab/page
        url:        The page URL (stored for reference)
        title:      The page title (stored for reference)
        content:    Raw extracted page text

    Returns:
        IndexResult with statistics about the operation
    """
    logger.info(f"Indexing page: '{title}' [{url}] (session: {session_id})")

    original_length = len(content)

    # Step 1: Clean the raw text
    logger.info("Step 1/3: Cleaning text...")
    cleaned = clean_text(content)
    text_stats = get_text_stats(cleaned)
    logger.info(f"  → {original_length} chars → {len(cleaned)} chars ({text_stats['words']} words)")

    if len(cleaned) < 100:
        raise ValueError(
            f"Page content too short after cleaning ({len(cleaned)} chars). "
            "The page may be mostly JavaScript, ads, or empty."
        )

    # Step 2: Split into chunks
    logger.info("Step 2/3: Chunking text...")
    chunks = chunk_text(cleaned)
    chunk_stats = get_chunk_stats(chunks)
    logger.info(f"  → {chunk_stats['count']} chunks (avg {chunk_stats['avg_length']} chars each)")

    if not chunks:
        raise ValueError("No chunks produced — page content may be too short or empty.")

    # Step 3: Embed and store in ChromaDB
    logger.info("Step 3/3: Embedding and storing chunks...")
    stored = store_chunks(session_id=session_id, chunks=chunks)
    logger.info(f"  → {stored} chunks stored in ChromaDB for session '{session_id}'")

    return IndexResult(
        session_id=session_id,
        url=url,
        original_length=original_length,
        cleaned_length=len(cleaned),
        chunks_created=stored,
        chunk_stats=chunk_stats,
    )


def retrieve(session_id: str, query: str, k: int = 4) -> RetrievalResult:
    """
    Retrieves the most relevant chunks for a given query.

    Called at question-answer time. The session_id must match
    the one used in index_page() for this page.

    In Phase 3, this is called inside the chat pipeline before
    passing context to Gemini.

    Args:
        session_id: Must match the session used when indexing
        query:      The user's question
        k:          Number of chunks to retrieve (default 4)

    Returns:
        RetrievalResult containing the matched chunks
    """
    logger.info(f"Retrieving for query: '{query[:60]}' (session: {session_id}, k={k})")

    chunks = search_chunks(session_id=session_id, query=query, k=k)

    logger.info(f"  → {len(chunks)} chunks retrieved")

    return RetrievalResult(
        session_id=session_id,
        query=query,
        chunks=chunks,
    )
