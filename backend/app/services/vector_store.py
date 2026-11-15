"""
vector_store.py — ChromaDB + Hybrid Search (dense vectors + BM25 keywords).

--- WHY HYBRID SEARCH? ---

  Dense (vector) search finds chunks by MEANING. It's great at
  "How do cars work?" → "Engines combust fuel". But it's weak at
  EXACT tokens: acronyms, product names, code, error messages,
  rare words. An embedding can blur "LSTM" into "neural network".

  BM25 is a keyword search algorithm (like the scoring engine behind
  classic search engines). It matches exact terms, rewarding chunks
  that contain the query's rare words. It's the perfect complement
  to vector search.

  Hybrid search = run BOTH, then merge the two rankings with
  Reciprocal Rank Fusion (RRF):

      RRF_score(chunk) = Σ  1 / (rrf_k + rank_i)

  where rank_i is the chunk's position in each result list. A chunk
  that ranks high in BOTH lists gets a big boost; a chunk that's
  only high in one list still survives. rrf_k=60 (standard) softens
  the advantage of rank #1 vs rank #5.

--- HOW IT WORKS HERE ---

  Dense vectors live in ChromaDB (as before). The BM25 index is
  rebuilt in-memory from the same chunks whenever we search —
  for a single-page session (a few hundred chunks) this is fast
  and avoids persisting a second index.
"""

import logging
import re

import chromadb
from langchain_community.vectorstores import Chroma
from rank_bm25 import BM25Okapi

from app.services.embedder import get_embeddings
from app.config import settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens for BM25. Keeps acronyms/numbers intact."""
    return _TOKEN_RE.findall(text.lower())


def _collection_name(session_id: str) -> str:
    """
    ChromaDB collection names must be 3-63 chars, alphanumeric + hyphens.
    We sanitize the session_id to meet these requirements.
    """
    safe = "".join(c if c.isalnum() else "-" for c in session_id)
    if safe[0].isdigit():
        safe = "s-" + safe
    return safe[:63]


def _client() -> "chromadb.api.ClientAPI":
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def store_chunks(session_id: str, chunks: list[str]) -> int:
    """
    Stores a list of text chunks in ChromaDB under the given session's collection.

    This REPLACES any existing data for this session — if the user
    revisits a page or refreshes, we start clean.

    Args:
        session_id: Unique ID for this page session (from the Chrome extension)
        chunks:     List of cleaned text chunks from chunker.py

    Returns:
        Number of chunks successfully stored.
    """
    collection = _collection_name(session_id)

    # Delete existing collection for this session (clean slate)
    _delete_collection(collection)

    metadatas = [
        {"chunk_index": i, "session_id": session_id}
        for i in range(len(chunks))
    ]

    Chroma.from_texts(
        texts=chunks,
        embedding=get_embeddings(),
        metadatas=metadatas,
        collection_name=collection,
        persist_directory=settings.chroma_persist_dir,
    )

    logger.info(f"Stored {len(chunks)} chunks in collection '{collection}'")
    return len(chunks)


def _dense_search(vectorstore: Chroma, query: str, k: int) -> list[tuple[str, dict]]:
    """Dense (semantic) search: returns (content, metadata) pairs."""
    docs = vectorstore.similarity_search(query=query, k=k)
    return [(doc.page_content, doc.metadata) for doc in docs]


def _bm25_search(all_chunks: list[tuple[str, dict]], query: str, k: int) -> list[tuple[str, dict]]:
    """Keyword (BM25) search over the session's chunks, in-memory."""
    if not all_chunks:
        return []

    corpus = [_tokenize(content) for content, _ in all_chunks]
    if not any(corpus):
        return []

    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))

    # Rank by score, keep only positive scores
    ranked = sorted(
        zip(scores, range(len(all_chunks))),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [
        (all_chunks[idx][0], all_chunks[idx][1])
        for score, idx in ranked[:k]
        if score > 0
    ]


def _reciprocal_rank_fusion(
    *ranked_lists: list[tuple[str, dict]],
    rrf_k: int = 60,
) -> list[tuple[str, dict]]:
    """
    Merges multiple ranked result lists into one using RRF.

    score(doc) = Σ 1 / (rrf_k + rank)  over every list it appears in.
    Ties (same content) accumulate scores from both lists — that's
    the point: agreement between dense and keyword search is signal.
    """
    scores: dict[str, float] = {}
    content_meta: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, (content, meta) in enumerate(ranked):
            key = content
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            if key not in content_meta:
                content_meta[key] = meta

    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(content, content_meta[content]) for content, _ in fused]


def _get_all_chunks(collection: str) -> list[tuple[str, dict]]:
    """Fetches every chunk (content + metadata) from the collection."""
    client = _client()
    col = client.get_or_create_collection(name=collection)
    data = col.get(include=["documents", "metadatas"])
    return list(zip(data["documents"], data["metadatas"]))


def search_chunks(session_id: str, query: str, k: int = 4) -> list[dict]:
    """
    Hybrid retrieval: dense vector search + BM25 keyword search,
    fused with Reciprocal Rank Fusion.

    Args:
        session_id: Must match the session_id used in store_chunks()
        query:      The user's question
        k:          How many fused candidates to return (before reranking)

    Returns:
        List of dicts with keys: 'content', 'chunk_index', 'score'
    """
    collection = _collection_name(session_id)
    vectorstore = Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_persist_dir,
    )

    # 1. Dense search — semantic meaning
    dense = _dense_search(vectorstore, query, k=settings.fetch_k)

    # 2. BM25 search — exact keyword matching
    all_chunks = _get_all_chunks(collection)
    keyword = _bm25_search(all_chunks, query, k=settings.bm25_k)

    # 3. Fuse the two rankings
    fused = _reciprocal_rank_fusion(dense, keyword, rrf_k=settings.rrf_k)
    top = fused[:k]

    results = [
        {
            "content": content,
            "chunk_index": meta.get("chunk_index", -1),
            "score": round(1.0 / (settings.rrf_k + rank + 1), 5),
        }
        for rank, (content, meta) in enumerate(top)
    ]

    logger.info(
        f"Hybrid search: dense={len(dense)} candidates, bm25={len(keyword)} "
        f"candidates → {len(results)} fused chunks for query "
        f"'{query[:50]}...' from session '{session_id}'"
    )
    return results


def _delete_collection(collection_name: str) -> None:
    """
    Deletes a ChromaDB collection if it exists.
    Called before re-indexing a page to avoid stale data.
    """
    try:
        client = _client()
        client.delete_collection(name=collection_name)
        logger.info(f"Deleted existing collection: '{collection_name}'")
    except Exception:
        # Collection didn't exist yet — that's fine
        pass
