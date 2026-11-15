"""
reranker.py — Cross-encoder reranking for retrieval results.

--- WHY A RERANKER? ---

  Bi-encoder (our embedding model) embeds the query and each chunk
  INDEPENDENTLY, then compares vectors. It's fast (you can precompute
  chunk vectors) but it never sees the query and chunk together, so
  it can miss subtle relevance.

  A cross-encoder feeds the pair [query, chunk] through the model
  TOGETHER and outputs a single relevance score. It sees every word
  interaction, so it's far more accurate — but it's O(n) model
  forward-passes per query, so it can't scan the whole corpus.

  The classic architecture:
      1. RETRIEVE   — hybrid search pulls a wide candidate set (cheap)
      2. RERANK     — cross-encoder scores the top candidates (accurate)
      3. TRUNCATE   — keep only the best few for the LLM

  We use `cross-encoder/ms-marco-MiniLM-L-6-v2`: a small, fast model
  trained on the MS MARCO passage-ranking dataset, running on CPU.
"""

import logging
from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """
    Returns the shared cross-encoder reranker (singleton, like the embedder).
    First call downloads the model (~90MB) and caches it locally.
    """
    logger.info(f"Loading reranker model: {settings.reranker_model}")

    model = CrossEncoder(
        settings.reranker_model,
        max_length=512,
        device="cpu",
    )

    logger.info("Reranker model loaded successfully")
    return model


def rerank(query: str, candidates: list[dict], top_k: int | None = None) -> list[dict]:
    """
    Reranks candidate chunks by cross-encoder relevance to the query.

    Args:
        query:      The user's question
        candidates: List of dicts with at least a 'content' key
                    (as returned by vector_store.search_chunks)
        top_k:      How many results to keep (defaults to settings.final_k)

    Returns:
        The same dicts, sorted by reranker score (descending), with an
        added 'rerank_score' key, truncated to top_k.
    """
    top_k = top_k or settings.final_k
    if not candidates:
        return []

    model = get_reranker()
    pairs = [(query, c["content"]) for c in candidates]
    scores = model.predict(pairs)

    scored = sorted(
        zip(candidates, scores),
        key=lambda pair: pair[1],
        reverse=True,
    )

    results = []
    for candidate, score in scored[:top_k]:
        out = dict(candidate)
        out["rerank_score"] = round(float(score), 4)
        results.append(out)

    logger.info(
        f"Reranked {len(candidates)} candidates → top {len(results)} "
        f"(scores: {[r['rerank_score'] for r in results]})"
    )
    return results
