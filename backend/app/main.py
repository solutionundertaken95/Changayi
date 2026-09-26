"""
main.py — FastAPI application entry point.

Phase 3 update: added the /api/chat route.

Full API surface:
  GET  /api/health        → confirm backend is running
  POST /api/page/index    → index a webpage (clean → chunk → embed → store)
  POST /api/page/search   → test retrieval (dev only)
  POST /api/chat          → ask a question (retrieve → prompt → Gemini → answer)
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.api.routes import page
from app.api.routes import chat

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG Chatbot API",
    description="Chrome Extension RAG Chatbot — Backend API",
    version="0.3.0",   # Phase 3
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(page.router,   prefix="/api", tags=["Page Indexing"])
app.include_router(chat.router,   prefix="/api", tags=["Chat"])

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "RAG Chatbot API is running",
        "version": "0.3.0",
        "docs": "/docs",
        "endpoints": {
            "health":       "GET  /api/health",
            "index_page":   "POST /api/page/index",
            "search_page":  "POST /api/page/search",
            "chat":         "POST /api/chat",
        },
    }
