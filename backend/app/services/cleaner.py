"""
cleaner.py — Cleans raw webpage text before it enters the RAG pipeline.

Why do we need a cleaner?
  The Chrome extension extracts text from the DOM, but webpages are messy:
    - Collapsed whitespace from CSS rendering
    - Navigation menu text mixed with article content
    - Cookie banners, "Subscribe now!" prompts
    - Repeated newlines from block elements
    - Unicode oddities (non-breaking spaces, soft hyphens)

  If we embed dirty text, our vector representations become noisy.
  Noisy embeddings → poor similarity search → bad answers.

  Analogy: Imagine trying to find a specific book in a library where
  random grocery lists are filed between the real books. The cleaner
  removes the grocery lists.

What we clean (in order):
  1. Normalize unicode (remove/replace weird characters)
  2. Collapse excessive whitespace and blank lines
  3. Remove lines that are clearly boilerplate (very short, repetitive)
  4. Strip leading/trailing whitespace

What we intentionally keep:
  - Sentence structure and punctuation (important for embeddings)
  - Paragraph breaks (helps chunking produce coherent pieces)
  - Numbers and dates (often meaningful in context)
"""

import re
import unicodedata


def clean_text(raw_text: str) -> str:
    """
    Takes raw extracted webpage text and returns clean, normalized text
    ready for chunking.

    Args:
        raw_text: The raw string from the Chrome extension's DOM extraction.

    Returns:
        Cleaned text string.
    """
    text = raw_text

    # Step 1: Normalize unicode
    # 'NFKC' normalization: converts special unicode chars to their
    # standard equivalents (e.g. non-breaking space → regular space,
    # curly quotes → straight quotes, ligatures → individual letters)
    text = unicodedata.normalize("NFKC", text)

    # Step 2: Replace common noise characters
    text = text.replace("\x00", "")          # Null bytes
    text = text.replace("\r\n", "\n")        # Windows line endings → Unix
    text = text.replace("\r", "\n")          # Old Mac line endings → Unix
    text = text.replace("\xa0", " ")         # Non-breaking spaces → regular space
    text = text.replace("​", "")        # Zero-width spaces (invisible!)
    text = text.replace("‌", "")        # Zero-width non-joiner
    text = text.replace("‍", "")        # Zero-width joiner

    # Step 3: Collapse long runs of whitespace within lines
    # "Hello    world" → "Hello world"
    text = re.sub(r"[ \t]+", " ", text)

    # Step 4: Remove lines that are just whitespace
    lines = text.split("\n")
    lines = [line.strip() for line in lines]

    # Step 5: Filter out very short lines that are likely navigation/UI noise
    # (e.g. "Menu", "Home", "▶", single-word nav items)
    # We keep lines with at least 20 characters OR that end with punctuation
    # to preserve short-but-meaningful lines like "Python is a language."
    meaningful_lines = []
    for line in lines:
        if not line:
            meaningful_lines.append("")      # Keep blank lines (paragraph breaks)
            continue
        if len(line) >= 20:
            meaningful_lines.append(line)
        elif line[-1] in ".!?:,;)\"'":      # Short but punctuated → keep
            meaningful_lines.append(line)
        # else: skip (likely a nav item, label, or button text)

    text = "\n".join(meaningful_lines)

    # Step 6: Collapse 3+ consecutive blank lines into just 2
    # Preserves paragraph structure without giant empty sections
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Step 7: Final strip
    text = text.strip()

    return text


def get_text_stats(text: str) -> dict:
    """
    Returns simple statistics about the cleaned text.
    Useful for logging and debugging.
    """
    lines = [l for l in text.split("\n") if l.strip()]
    words = text.split()
    return {
        "characters": len(text),
        "words": len(words),
        "lines": len(lines),
        "estimated_tokens": len(words) * 1.3,  # rough estimate: 1 word ≈ 1.3 tokens
    }
