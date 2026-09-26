"""
schemas.py — All Pydantic request and response models for the RAG pipeline.

Why Pydantic?
  FastAPI uses Pydantic models to:
    1. Validate incoming JSON automatically (wrong types → 422 error with clear message)
    2. Auto-generate the /docs Swagger UI with example payloads
    3. Serialize Python objects → JSON for responses

  Think of these as "contracts" between the frontend and backend.
  If the Chrome extension sends { session_id: 123 } and we expect a string,
  Pydantic catches it immediately with a helpful error.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Page Indexing — POST /api/page/index
# ---------------------------------------------------------------------------

class IndexPageRequest(BaseModel):
    """
    Sent by the Chrome extension when a user opens the chatbot on a new page.
    The extension extracts the page text and sends it here for RAG processing.
    """
    session_id: str = Field(
        ...,
        description="Unique identifier for this tab/page session",
        example="tab_1234567890"
    )
    url: str = Field(
        ...,
        description="The full URL of the current webpage",
        example="https://en.wikipedia.org/wiki/Python_(programming_language)"
    )
    title: str = Field(
        ...,
        description="The page <title>",
        example="Python (programming language) - Wikipedia"
    )
    content: str = Field(
        ...,
        description="Raw extracted text from the webpage DOM",
        min_length=50   # Reject pages with almost no content
    )


class IndexPageResponse(BaseModel):
    """Returned after the page has been cleaned, chunked, embedded, and stored."""
    success: bool
    message: str
    session_id: str
    chunks_created: int = Field(description="How many text chunks were stored in ChromaDB")
    url: str


# ---------------------------------------------------------------------------
# Search / Retrieval — POST /api/page/search (Phase 2 testing only)
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """
    Test endpoint to verify retrieval works before adding Gemini in Phase 3.
    The Chrome extension won't call this directly — it goes through /api/chat.
    """
    session_id: str
    query: str = Field(..., min_length=3, example="What is this page about?")
    k: int = Field(default=4, ge=1, le=10, description="Number of chunks to retrieve")


class RetrievedChunk(BaseModel):
    """A single chunk returned by the similarity search."""
    content: str = Field(description="The actual text of the chunk")
    chunk_index: int = Field(description="Position of this chunk in the original document")


class SearchResponse(BaseModel):
    """Returned by the search endpoint — shows the top-k most relevant chunks."""
    session_id: str
    query: str
    results: list[RetrievedChunk]
    total_found: int


# ---------------------------------------------------------------------------
# Chat — POST /api/chat  (used in Phase 3 with Gemini)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Sent by the Chrome extension when the user types a question."""
    session_id: str
    question: str = Field(..., min_length=3, example="What are the main topics on this page?")


class Source(BaseModel):
    """A source chunk that contributed to the AI's answer."""
    content: str
    chunk_index: int


class ChatResponse(BaseModel):
    """Returned after the full RAG pipeline: retrieve chunks → prompt Gemini → respond."""
    session_id: str
    question: str
    answer: str
    sources: list[Source]
