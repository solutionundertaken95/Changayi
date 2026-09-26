"""
chat.py — POST /api/chat endpoint.

This is the endpoint the Chrome extension calls when the user
sends a message in the chatbot panel.

Request flow:
  Chrome Extension
    POST /api/chat { session_id, question }
       │
       ▼
  chat_service.chat()
       ├── rag_service.retrieve()   → ChromaDB similarity search
       └── llm_service.generate_answer()  → Gemini API
       │
       ▼
  ChatResponse { session_id, question, answer, sources }
       │
       ▼
  Chrome Extension renders answer in chat UI
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, Source
from app.services import chat_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Runs the full RAG pipeline for a user's question:
      1. Retrieves relevant chunks from ChromaDB (using session_id)
      2. Builds a RAG prompt with those chunks
      3. Sends the prompt to Gemini
      4. Returns the answer and the source chunks used

    The session_id in the request must match the session_id that was
    used when the page was indexed via POST /api/page/index.
    """
    logger.info(
        f"Chat request | session='{request.session_id}' | "
        f"question='{request.question[:60]}'"
    )

    try:
        result = chat_service.chat(
            session_id=request.session_id,
            question=request.question,
        )

        return ChatResponse(
            session_id=result.session_id,
            question=result.question,
            answer=result.answer,
            sources=[
                Source(
                    content=s["content"],
                    chunk_index=s["chunk_index"],
                )
                for s in result.sources
            ],
        )

    except ValueError as e:
        logger.warning(f"Chat validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate answer: {str(e)}"
        )
