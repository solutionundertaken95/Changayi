"""
chunker.py — Semantic + Structure-aware chunking.

--- THE OLD STRATEGY (what we replaced) ---

  RecursiveCharacterTextSplitter: split on character counts, trying
  "\n\n", "\n", ". " etc. as fallback boundaries. It knows nothing
  about what the text MEANS or where sections begin/end — it can
  split a paragraph in half, or merge two unrelated sections.

--- THE NEW STRATEGY ---

  1. STRUCTURE-AWARE SEGMENTATION
     Web pages are not flat text. They have headings, lists, and
     paragraphs. We first split the cleaned text into *sections*:

       - A heading line (e.g. "## History", "History", "1. Intro")
         starts a new section; everything after it belongs to it.
       - Each section gets a heading "breadcrumb" prefixed to its
         chunks (e.g. "History > Post-war era\n\n...") so the
         embedding captures the section's context, not just the
         raw paragraph. This is critical: a chunk that says
         "The war ended in 1945" is ambiguous without its heading.

  2. SEMANTIC CHUNKING
     Within a section, we split into sentences and greedily build
     chunks, but we only merge two sentences into the same chunk if
     their embedding cosine similarity is above a threshold. If
     sentence B drifts away from the running chunk's topic, we start
     a new chunk — even if the current chunk is still small.

     This keeps chunks *topically coherent*, which is what makes
     retrieval precise: a chunk about one topic has one clear
     embedding, instead of a blurry average of two topics.

  3. SIZE GUARDRAILS
     Semantic boundaries are still clamped to [min, max] characters
     so we never get one-sentence chunks or page-sized chunks.
"""

import logging
import re

from app.config import settings
from app.services.embedder import embed_texts

logger = logging.getLogger(__name__)

# A line that looks like a heading: markdown headers, "1. Title",
# "Title:", ALL-CAPS short lines, or short lines without ending punctuation.
_HEADING_RE = re.compile(
    r"^(#{1,6}\s+.+|"                 # markdown headers
    r"\d+(\.\d+)*\.?\s+\S.*|"         # numbered sections "1. / 2.3"
    r"[A-Z][^.!?]{0,80}:$|"           # "Some Title:"
    r"[A-Z][A-Z0-9 ,&'\-]{2,60}$)"    # ALL CAPS LINE
)

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_LIST_ITEM_RE = re.compile(r"^(\s*[-*•\u2022]\s+|\s*\d+[.)]\s+)")


def _is_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 90:
        return False
    # A heading is short and does NOT end with sentence punctuation
    # (the "Title:" variant above is the exception).
    if _HEADING_RE.match(line):
        return True
    words = line.split()
    return len(words) <= 8 and not line.endswith((".", "!", "?", ",", ";"))


def _split_sentences(text: str) -> list[str]:
    """Splits a section body into sentences, keeping list items whole."""
    sentences: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # List items are atomic — don't split them into sentences
        if _LIST_ITEM_RE.match(line):
            sentences.append(line)
            continue
        sentences.extend(s.strip() for s in _SENT_SPLIT_RE.split(line) if s.strip())
    return sentences


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot  # vectors are L2-normalized by the embedder, so dot == cosine


def _semantic_split(
    sentences: list[str],
    min_size: int,
    max_size: int,
    similarity_threshold: float,
) -> list[str]:
    """
    Greedy semantic chunking inside one section.

    For each new sentence, compare its embedding with the embedding of
    the current chunk's *first* sentence (the anchor = the topic).
    If similarity drops below the threshold → start a new chunk.
    Otherwise append, until the chunk hits max_size.
    """
    if not sentences:
        return []

    vectors = embed_texts(sentences)

    chunks: list[str] = []
    current: list[str] = [sentences[0]]
    current_len = len(sentences[0])
    anchor_vec = vectors[0]

    for sent, vec in zip(sentences[1:], vectors[1:]):
        same_topic = _cosine(anchor_vec, vec) >= similarity_threshold
        fits = current_len + 1 + len(sent) <= max_size

        if same_topic and fits:
            current.append(sent)
            current_len += 1 + len(sent)
        else:
            # Flush the current chunk (if it's big enough) or keep it
            # and try to merge with the next sentence first.
            chunk_text = " ".join(current)
            if current_len >= min_size or not same_topic:
                chunks.append(chunk_text)
                current = [sent]
                current_len = len(sent)
                anchor_vec = vec
            else:
                # Too small to flush, but the topic drifted: still flush
                # to avoid stitching unrelated topics together.
                chunks.append(chunk_text)
                current = [sent]
                current_len = len(sent)
                anchor_vec = vec

    if current:
        chunks.append(" ".join(current))

    # Merge any trailing chunk that is too small into its predecessor
    if len(chunks) > 1 and len(chunks[-1]) < min_size:
        chunks[-2] += " " + chunks.pop(-1)

    return chunks


def chunk_text(text: str, max_size: int | None = None) -> list[str]:
    """
    Splits cleaned text into structure-aware, semantically coherent chunks.

    Args:
        text:     Cleaned page text from cleaner.py
        max_size: Max characters per chunk (defaults to settings.chunk_size)

    Returns:
        List of chunk strings. Each chunk is prefixed with the heading
        breadcrumb of the section it belongs to.
    """
    max_size = max_size or settings.chunk_size
    min_size = max(60, max_size // 3)

    # --- 1. Segment into sections by heading ---
    sections: list[tuple[list[str], str]] = []  # (heading_parts, body)
    current_headings: list[str] = []
    current_body: list[str] = []

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if _is_heading(line):
            if current_body:
                sections.append((current_headings, "\n".join(current_body)))
                current_body = []
            # Keep the heading hierarchy shallow (last 2 levels)
            current_headings = (current_headings + [line])[-2:]
        else:
            current_body.append(line)

    if current_body:
        sections.append((current_headings, "\n".join(current_body)))

    # Fallback: no headings detected at all → treat whole page as one section
    if not sections:
        sections = [([], text)]

    # --- 2. Semantic chunking within each section ---
    chunks: list[str] = []
    for headings, body in sections:
        breadcrumb = " > ".join(headings[-2:])
        sentences = _split_sentences(body)
        if not sentences:
            continue

        # Very short sections (a heading + one sentence) are kept whole
        if len(body) <= max_size:
            section_chunks = [body]
        else:
            section_chunks = _semantic_split(
                sentences,
                min_size=min_size,
                max_size=max_size,
                similarity_threshold=settings.semantic_similarity_threshold,
            )

        for chunk in section_chunks:
            chunk = chunk.strip()
            if len(chunk) < 30:
                continue
            if breadcrumb:
                chunks.append(f"{breadcrumb}\n{chunk}")
            else:
                chunks.append(chunk)

    logger.info(
        f"Chunked text: {len(text)} chars → {len(chunks)} chunks "
        f"(semantic+structure, max_size={max_size}, "
        f"threshold={settings.semantic_similarity_threshold}, "
        f"{len(sections)} sections)"
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
