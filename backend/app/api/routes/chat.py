"""
chat.py — POST /api/chat  and  POST /api/chat/stream  endpoints.

POST /api/chat:
  Runs the full RAG pipeline and returns a complete ChatResponse JSON.
  Used by sendMessage() in the extension for compatibility.

POST /api/chat/stream (Phase 8):
  Same RAG pipeline but streams the Gemini answer via Server-Sent Events
  (SSE) so the React UI can display tokens as they arrive.
"""

import asyncio
import json as _json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse, Source
from app.services import chat_service, rag_service
from app.services.llm_service import generate_answer_stream

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


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Streaming version of POST /api/chat (Phase 8).

    Instead of waiting for the full Gemini response and returning it as one
    JSON blob, this endpoint sends Server-Sent Events (SSE) so the React UI
    can display the answer as it is being generated — word by word.

    SSE message protocol
    --------------------
    Each event is a line of the form:

        data: <JSON>\n\n

    The JSON object always has a "type" field:

        {"type": "sources", "sources": [...]}   <- sent first
        {"type": "chunk",   "text": "Hello"}    <- one per Gemini chunk
        {"type": "done"}                         <- signals end of stream
        {"type": "error",   "message": "..."}   <- sent if something fails

    Why SSE instead of WebSockets?
    --------------------------------
    SSE (text/event-stream) is a one-directional push from server to client
    over a regular HTTP connection. It is simpler than WebSockets for this
    use-case because we only need one direction: the server streams the
    answer, the client just reads it. Works fine inside Chrome extensions.
    """
    async def event_generator():
        try:
            # Step 1: Retrieve relevant chunks
            # rag_service.retrieve() is synchronous (ChromaDB is sync).
            # asyncio.to_thread() runs it in a thread pool so the async
            # event loop is not blocked while ChromaDB does its search.
            retrieval = await asyncio.to_thread(
                rag_service.retrieve,
                request.session_id,
                request.question,
                4,
            )

            if not retrieval.chunks:
                no_ctx = (
                    "It looks like this page hasn't been analyzed yet. "
                    "Please wait a moment while I read the page, then try again."
                )
                yield f'data: {_json.dumps({"type": "sources", "sources": []})}' + "\n\n"
                yield f'data: {_json.dumps({"type": "chunk", "text": no_ctx})}' + "\n\n"
                yield f'data: {_json.dumps({"type": "done"})}' + "\n\n"
                return

            # Step 2: Send sources immediately so the UI can show them
            # before the answer even starts streaming.
            sources_payload = [
                {"content": c["content"], "chunk_index": c["chunk_index"]}
                for c in retrieval.chunks
            ]
            yield f'data: {_json.dumps({"type": "sources", "sources": sources_payload})}' + "\n\n"

            # Step 3: Stream Gemini answer chunk by chunk
            context_chunks = [c["content"] for c in retrieval.chunks]
            gen = generate_answer_stream(context_chunks, request.question)

            # generate_answer_stream is a synchronous Python generator.
            # We iterate it by calling next() inside run_in_executor so
            # each blocking Gemini network read happens in a thread.
            _DONE = object()
            loop = asyncio.get_event_loop()
            while True:
                text_chunk = await loop.run_in_executor(None, next, gen, _DONE)
                if text_chunk is _DONE:
                    break
                if text_chunk:
                    yield f'data: {_json.dumps({"type": "chunk", "text": text_chunk})}' + "\n\n"

            yield f'data: {_json.dumps({"type": "done"})}' + "\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f'data: {_json.dumps({"type": "error", "message": str(e)})}' + "\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
