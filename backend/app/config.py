"""
config.py — Central configuration for the backend.

Why does this file exist?
  Instead of scattering os.getenv() calls all over the codebase,
  we load all environment variables in one place using Pydantic's
  BaseSettings. If a required variable is missing, the app fails
  immediately with a clear error — not silently mid-request.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    All configuration comes from the .env file (or real environment variables).
    Pydantic reads them automatically — no manual os.getenv() needed.
    """

    # --- API Keys ---
    # We'll add GEMINI_API_KEY here in Phase 3
    gemini_api_key: str = ""

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000

    # --- ChromaDB ---
    chroma_persist_dir: str = "./chroma_data"

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- Chunking defaults ---
    chunk_size: int = 500
    chunk_overlap: int = 50

    # --- Semantic chunking ---
    # Minimum cosine similarity for two sentences to share a chunk
    semantic_similarity_threshold: float = 0.55

    # --- Hybrid search ---
    # fetch_k: how many candidates the vector search pulls before fusion
    # bm25_k:  how many candidates BM25 keyword search pulls
    # Both candidate lists are merged with Reciprocal Rank Fusion (RRF)
    fetch_k: int = 12
    bm25_k: int = 8
    rrf_k: int = 60  # standard RRF constant

    # --- Reranking ---
    # Cross-encoder model that scores (query, chunk) pairs directly
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 8  # how many fused candidates to rerank
    final_k: int = 4            # how many chunks to finally send to the LLM

    # --- Workspaces (multi-tab knowledge bases) ---
    workspace_store_dir: str = "./data/workspaces"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Single shared instance — import this anywhere in the app
settings = Settings()
