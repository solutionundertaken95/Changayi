"""
vector_store.py — ChromaDB integration for storing and retrieving page chunks.

--- WHAT IS A VECTOR DATABASE? ---

  A regular database stores text, numbers, dates.
  To find something, you match exact values: WHERE name = 'Alice'.

  A vector database stores embedding vectors alongside the text.
  To find something, you search by MEANING:
    "Find the chunks most similar to this question's embedding."

  Under the hood, ChromaDB computes the cosine similarity between
  the query vector and every stored chunk vector, then returns
  the top-k closest matches. This is called ANN (Approximate
  Nearest Neighbor) search.

--- COSINE SIMILARITY ---

  Imagine two arrows pointing from the origin in 384-dimensional space.
  Cosine similarity measures the angle between the arrows:
    - Angle = 0°  → cosine = 1.0 → identical meaning
    - Angle = 90° → cosine = 0.0 → unrelated meaning
    - Angle = 180°→ cosine = -1.0 → opposite meaning

--- PER-SESSION COLLECTIONS ---

  The user might open the chatbot on Wikipedia, ask questions,
  then switch to a news article and ask more questions.

  We CANNOT mix the chunks from those two pages — the answers would
  be nonsense ("According to the Wikipedia article... [but the user
  asked about the news article]").

  Solution: each page gets its own ChromaDB "collection" named by
  session_id. When a user visits a new page, we clear the old
  collection and create a fresh one.
"""

import logging
from langchain_community.vectorstores import Chroma

from app.services.embedder import get_embeddings
from app.config import settings

logger = logging.getLogger(__name__)


def _collection_name(session_id: str) -> str:
    """
    ChromaDB collection names must be 3-63 chars, alphanumeric + hyphens.
    We sanitize the session_id to meet these requirements.
    """
    # Replace any non-alphanumeric chars with hyphens
    safe = "".join(c if c.isalnum() else "-" for c in session_id)
    # Ensure it starts with a letter (ChromaDB requirement)
    if safe[0].isdigit():
        safe = "s-" + safe
    return safe[:63]   # Max 63 chars


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

    # Add metadata to each chunk so we can reference them later
    # metadatas[i] corresponds to chunks[i]
    metadatas = [
        {"chunk_index": i, "session_id": session_id}
        for i in range(len(chunks))
    ]

    # Chroma.from_texts() does three things in one call:
    #   1. Embeds all the chunks using our HuggingFace model
    #   2. Creates a ChromaDB collection
    #   3. Stores chunks + embeddings + metadata together
    Chroma.from_texts(
        texts=chunks,
        embedding=get_embeddings(),
        metadatas=metadatas,
        collection_name=collection,
        persist_directory=settings.chroma_persist_dir,
    )

    logger.info(f"Stored {len(chunks)} chunks in collection '{collection}'")
    return len(chunks)


def search_chunks(session_id: str, query: str, k: int = 4) -> list[dict]:
    """
    Finds the k most semantically similar chunks to the query.

    Process:
      1. Embed the query using the same model used for indexing
      2. Compute cosine similarity between query embedding and all chunk embeddings
      3. Return the top-k chunks

    Args:
        session_id: Must match the session_id used in store_chunks()
        query:      The user's question
        k:          How many chunks to retrieve (default 4)

    Returns:
        List of dicts with keys: 'content', 'chunk_index'
    """
    collection = _collection_name(session_id)

    # Load the existing collection (it was stored in store_chunks)
    vectorstore = Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_persist_dir,
    )

    # similarity_search returns LangChain Document objects
    # Each Document has: .page_content (the chunk text), .metadata (our dict)
    docs = vectorstore.similarity_search(query=query, k=k)

    results = [
        {
            "content": doc.page_content,
            "chunk_index": doc.metadata.get("chunk_index", -1),
        }
        for doc in docs
    ]

    logger.info(
        f"Retrieved {len(results)} chunks for query '{query[:50]}...' "
        f"from session '{session_id}'"
    )
    return results


def _delete_collection(collection_name: str) -> None:
    """
    Deletes a ChromaDB collection if it exists.
    Called before re-indexing a page to avoid stale data.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        client.delete_collection(name=collection_name)
        logger.info(f"Deleted existing collection: '{collection_name}'")
    except Exception:
        # Collection didn't exist yet — that's fine
        pass
