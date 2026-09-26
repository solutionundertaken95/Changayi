"""
page.py — API routes for page indexing and retrieval testing.

Endpoints:
  POST /api/page/index   — index a webpage (called by Chrome extension)
  POST /api/page/search  — test retrieval (for development/testing only)

Why separate index and search?
  In Phase 3, the Chrome extension will only use:
    - POST /api/page/index  (when chatbot opens on a new page)
    - POST /api/chat        (when user sends a message)

  The /api/page/search endpoint is a DEVELOPMENT TOOL — it lets you
  verify that retrieval is working correctly through Swagger UI
  BEFORE adding Gemini. This follows the project's "test each
  layer independently" principle.
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    IndexPageRequest,
    IndexPageResponse,
    SearchRequest,
    SearchResponse,
    RetrievedChunk,
)
from app.services import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/page/index", response_model=IndexPageResponse)
async def index_page(request: IndexPageRequest) -> IndexPageResponse:
    """
    Receives a webpage's content from the Chrome extension and runs the full
    indexing pipeline: clean → chunk → embed → store in ChromaDB.

    This endpoint should be called:
      - When the user opens the chatbot on a new page
      - When the user navigates to a new URL
      - When the user manually requests a re-index

    The session_id ties all subsequent chat messages to this page's data.
    """
    logger.info(
        f"Index request: session='{request.session_id}' | "
        f"url='{request.url}' | content_length={len(request.content)}"
    )

    try:
        result = rag_service.index_page(
            session_id=request.session_id,
            url=request.url,
            title=request.title,
            content=request.content,
        )

        return IndexPageResponse(
            success=True,
            message=f"Successfully indexed '{request.title}' — {result.chunks_created} chunks stored",
            session_id=result.session_id,
            chunks_created=result.chunks_created,
            url=result.url,
        )

    except ValueError as e:
        # Content was too short or empty after cleaning
        logger.warning(f"Indexing failed (bad content): {e}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        # Unexpected error — log it and return 500
        logger.error(f"Indexing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index page: {str(e)}"
        )


@router.post("/page/search", response_model=SearchResponse)
async def search_page(request: SearchRequest) -> SearchResponse:
    """
    TEST ENDPOINT — verifies that retrieval is working correctly.

    Use this through Swagger UI (/docs) to:
      1. First index a page via /api/page/index
      2. Then query it here to see which chunks are retrieved
      3. Confirm the retrieved chunks are relevant to your question

    This endpoint is for development only — in production, retrieval
    happens internally inside /api/chat (Phase 3).
    """
    logger.info(
        f"Search request: session='{request.session_id}' | "
        f"query='{request.query}' | k={request.k}"
    )

    try:
        result = rag_service.retrieve(
            session_id=request.session_id,
            query=request.query,
            k=request.k,
        )

        chunks = [
            RetrievedChunk(
                content=c["content"],
                chunk_index=c["chunk_index"],
            )
            for c in result.chunks
        ]

        return SearchResponse(
            session_id=result.session_id,
            query=result.query,
            results=chunks,
            total_found=len(chunks),
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )
