"""
chunker.py — Splits cleaned webpage text into chunks for embedding.

--- THE CORE CONCEPT ---

Why do we split text into chunks?

  Analogy: Imagine a library book with 500 pages. If you summarize
  the entire book as ONE sentence, you lose all the detail. But if
  you summarize it page-by-page, you can find exactly the right page
  for any question.

  An embedding model does something similar: it compresses text into
  a single vector (a list of numbers that represents meaning).
  If you embed an entire 10,000-word webpage as one vector, the
  resulting number represents an "average" of all the content — too
  vague to retrieve specific information reliably.

  Chunks = specific, focused pieces of text.
  Each chunk gets its OWN embedding → more precise retrieval.

--- KEY PARAMETERS ---

chunk_size (default: 500 characters):
  The maximum size of each chunk. Larger chunks = more context per
  chunk, but less precise retrieval. Smaller = more precise, but
  risks splitting mid-sentence.

  Characters, not words. 500 chars ≈ 80-100 words ≈ 3-5 sentences.

chunk_overlap (default: 50 characters):
  How many characters of the previous chunk are repeated at the start
  of the next chunk.

  Why overlap?
  If a key fact spans the boundary between chunk 3 and chunk 4,
  without overlap, that fact gets split and neither chunk has the
  full context. With overlap, both chunks contain part of it —
  retrieval is more robust.

  Example (chunk_size=20, overlap=5):
    Text:     "The quick brown fox jumps over the lazy dog"
    Chunk 1:  "The quick brown fox "
    Chunk 2:  " fox jumps over the "   ← starts 5 chars before chunk 1 ended
    Chunk 3:  " the lazy dog"

--- WHY RecursiveCharacterTextSplitter? ---

LangChain offers several splitters. This one is the most intelligent
for general text because it tries to split on natural boundaries first:

  Priority order:
    1. Paragraph breaks ("\n\n")   ← best — full paragraph is coherent
    2. Line breaks ("\n")
    3. Sentence ends (". ")
    4. Words (" ")
    5. Characters                  ← worst — only if nothing else works

  It only goes to the next level if the current chunk would exceed chunk_size.
"""

import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[str]:
    """
    Splits cleaned text into a list of overlapping chunks.

    Args:
        text:          Cleaned page text from cleaner.py
        chunk_size:    Max characters per chunk (defaults to settings.chunk_size)
        chunk_overlap: Overlap characters between chunks (defaults to settings.chunk_overlap)

    Returns:
        List of text chunk strings, each ≤ chunk_size characters.
    """
    size    = chunk_size    or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        # These separators are tried in order (most to least preferred)
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
        length_function=len,           # Measure by character count
        is_separator_regex=False,      # Treat separators as literal strings
    )

    chunks = splitter.split_text(text)

    # Filter out any chunks that are too short to be meaningful
    # (e.g. a lone heading or a separator that became its own chunk)
    chunks = [c.strip() for c in chunks if len(c.strip()) > 30]

    logger.info(
        f"Chunked text: {len(text)} chars → {len(chunks)} chunks "
        f"(size={size}, overlap={overlap})"
    )

    return chunks


def get_chunk_stats(chunks: list[str]) -> dict:
    """Returns statistics about the chunks for logging/debugging."""
    if not chunks:
        return {"count": 0, "avg_length": 0, "min_length": 0, "max_length": 0}

    lengths = [len(c) for c in chunks]
    return {
        "count": len(chunks),
        "avg_length": round(sum(lengths) / len(lengths)),
        "min_length": min(lengths),
        "max_length": max(lengths),
    }
