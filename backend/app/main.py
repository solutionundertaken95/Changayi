"""
main.py — FastAPI application entry point.

This is the file that starts everything.
Think of it as the front door of the backend:
  - It creates the FastAPI app
  - It registers all the API routes (health, page indexing, chat)
  - It configures CORS so the Chrome extension can talk to it
  - It will eventually start the ChromaDB and embedding services

How data flows:
  Chrome Extension  →  POST /api/...  →  FastAPI  →  Services  →  Response
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG Chatbot API",
    description="Backend for the Chrome Extension RAG Chatbot",
    version="0.1.0",
    docs_url="/docs",       # Swagger UI — visit this in your browser to test APIs
    redoc_url="/redoc",     # Alternative API docs
)

# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing)
# ---------------------------------------------------------------------------
# Why do we need this?
#   The Chrome extension runs on arbitrary webpages (e.g. https://bbc.com).
#   Browsers block requests to a different origin by default.
#   CORS headers tell the browser: "yes, this backend allows requests
#   from these origins."
#
#   In development we allow all origins ("*").
#   In production, you'd restrict this to your extension's origin.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Allow all origins in dev
    allow_credentials=True,
    allow_methods=["*"],           # Allow GET, POST, DELETE, etc.
    allow_headers=["*"],           # Allow all headers
)

# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------
# Each router is a group of related endpoints.
# We'll add more routers in Phase 2 (page indexing) and Phase 3 (chat).

app.include_router(health.router, prefix="/api", tags=["Health"])


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Simple root endpoint to confirm the server is running."""
    return {
        "message": "RAG Chatbot API is running",
        "docs": "/docs",
        "health": "/api/health",
    }
