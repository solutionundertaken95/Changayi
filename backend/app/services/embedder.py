"""
embedder.py — Loads and manages the HuggingFace embedding model.

--- WHAT ARE EMBEDDINGS? ---

  Analogy: A "meaning map."

  Imagine you have a huge map where every possible sentence has a location.
  Sentences with similar meaning are placed close together on this map.
  Sentences with different meaning are placed far apart.

  "How does a car engine work?"    → coordinates: [0.12, -0.43, 0.77, ...]
  "What powers an automobile?"     → coordinates: [0.14, -0.41, 0.79, ...]  ← CLOSE
  "What is the recipe for pasta?"  → coordinates: [-0.82, 0.31, -0.15, ...] ← FAR

  These "coordinates" are what we call embeddings: lists of numbers
  (vectors) that represent the meaning of text.

  When a user asks "How does a car engine work?", we:
    1. Convert the question to an embedding (its coordinates on the map)
    2. Find which stored chunks have the closest coordinates (similar meaning)
    3. Return those chunks as context for the LLM

  This is called "semantic search" — finding meaning, not just keywords.

--- WHY all-MiniLM-L6-v2? ---

  This is a small, fast, free HuggingFace model that:
    - Runs entirely on your local CPU (no GPU needed, no API key)
    - Produces 384-dimensional vectors
    - Is well-optimized for semantic similarity tasks
    - Downloads once (~90MB) and is cached locally

  Larger models produce better embeddings, but this one is the
  ideal balance of quality vs. speed for a local portfolio project.

--- SINGLETON PATTERN ---

  Loading a machine learning model from disk takes 2-5 seconds.
  If we load it on every API request, the chatbot would be very slow.

  Solution: load it ONCE when the backend starts, keep it in memory,
  and reuse the same instance for all requests.

  This is the "singleton" pattern — one shared instance.
"""

import logging
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Returns the shared HuggingFace embedding model instance.

    @lru_cache(maxsize=1) ensures this function only runs ONCE,
    no matter how many times it's called. Every subsequent call
    returns the same cached object instantly.

    The model is downloaded from HuggingFace Hub on first run
    and cached in ~/.cache/huggingface/ for future use.
    """
    logger.info(f"Loading embedding model: {settings.embedding_model}")
    logger.info("First load may take 30-60 seconds (downloading model)...")

    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={
            "device": "cpu",   # Use CPU — no GPU required
        },
        encode_kwargs={
            "normalize_embeddings": True,   # L2 normalize → cosine similarity works cleanly
            "batch_size": 32,               # Process 32 chunks at a time
        },
    )

    logger.info(f"Embedding model loaded successfully: {settings.embedding_model}")
    return embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Converts a list of text strings into a list of embedding vectors.

    Args:
        texts: List of text strings to embed (e.g. your chunks)

    Returns:
        List of vectors. Each vector is a list of 384 floats.
        The i-th vector corresponds to the i-th input text.

    Example:
        embed_texts(["Hello world", "Python programming"])
        → [[0.12, -0.43, ...], [0.55, 0.22, ...]]
    """
    model = get_embeddings()
    return model.embed_documents(texts)


def embed_query(query: str) -> list[float]:
    """
    Converts a single query string into an embedding vector.

    This is used at search time — we embed the user's question
    so we can compare it against the stored chunk embeddings.

    Args:
        query: The user's question string

    Returns:
        A single vector (list of 384 floats)
    """
    model = get_embeddings()
    return model.embed_query(query)
