"""
main.py — FastAPI application entry point.

Updated in Phase 2: added the page indexing routes.

How data flows:
  Chrome Extension → POST /api/page/index → page.py → rag_service.py
                                                        ├── cleaner.py
                                                        ├── chunker.py
                                                        └── vector_store.py (ChromaDB)

  Chrome Extension → POST /api/chat → chat.py (Phase 3) → rag_service.py → Gemini
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.api.routes import page

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
# This makes all our logger.info() / logger.error() calls visible in the
# terminal when you run the backend. Very helpful during development.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG Chatbot API",
    description="Chrome Extension RAG Chatbot — Backend API",
    version="0.2.0",   # Phase 2
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
# Phase 3 will add: app.include_router(chat.router, prefix="/api", tags=["Chat"])


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "RAG Chatbot API is running",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "health":      "GET  /api/health",
            "index_page":  "POST /api/page/index",
            "search_page": "POST /api/page/search",
        },
    }
