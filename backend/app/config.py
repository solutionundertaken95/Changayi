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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Single shared instance — import this anywhere in the app
settings = Settings()
