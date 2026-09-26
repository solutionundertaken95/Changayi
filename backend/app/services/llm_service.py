"""
llm_service.py — Gemini LLM integration for the RAG pipeline.

--- WHERE GEMINI FITS IN THE ARCHITECTURE ---

  ChromaDB retrieves relevant chunks  ←  this was Phase 2
           │
           ▼
  llm_service builds a RAG prompt
           │
           ▼
  Gemini reads the prompt and generates an answer
           │
           ▼
  Answer + sources returned to React

--- WHY A SEPARATE LLM SERVICE? ---

  The project instructions say: "structure the backend so that changing
  LLM providers does not require rewriting the entire RAG system."

  By isolating Gemini in this file, if you later want to add OpenAI
  as an alternative, you only change this one file.
  The chat_service.py that calls us doesn't need to know which LLM
  is underneath — it just calls generate_answer() and gets text back.

--- TEMPERATURE ---

  Temperature controls how "creative" vs "deterministic" the model is.
    - 0.0 = fully deterministic, same answer every time
    - 1.0 = very creative, different answer each time
    - 0.1 = slightly variable but mostly factual (ideal for RAG)

  For a question-answering assistant grounded in a specific webpage,
  we want the model to be precise and stick to the facts — not creative.

--- THE RAG PROMPT STRUCTURE ---

  The quality of a RAG system is largely determined by prompt design.

  Our prompt follows this structure:

    [System instruction]
      → Tells Gemini its role and strict rules
      → Most important rule: answer ONLY from the context provided
      → If the context doesn't have the answer, say so honestly

    [Retrieved context]
      → The 4 most relevant chunks from ChromaDB
      → Clearly delimited so Gemini knows what's "the page" vs "the question"

    [User question]
      → The actual question typed by the user

  This structure is called "stuffing" — we stuff the context into the prompt.
  It's the simplest and most reliable RAG approach for a single-page chatbot.
"""

import logging
from functools import lru_cache

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini model singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_model() -> genai.GenerativeModel:
    """
    Initializes and caches the Gemini model.
    Called once on first request, reused for all subsequent requests.
    """
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set in your .env file. "
            "Get one free at https://aistudio.google.com/app/apikey"
        )

    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name="gemini-3.7-flash",   # Fast, capable, generous free tier
        generation_config=genai.GenerationConfig(
            temperature=0.1,             # Low = factual, consistent answers
            max_output_tokens=1024,      # Enough for a thorough answer
            top_p=0.8,                   # Nucleus sampling — keeps answers focused
        ),
    )

    logger.info("Gemini model initialized: gemini-3.7-flash")
    return model


# ---------------------------------------------------------------------------
# RAG Prompt Builder
# ---------------------------------------------------------------------------

def _build_rag_prompt(context_chunks: list[str], question: str) -> str:
    """
    Constructs the full RAG prompt sent to Gemini.

    The prompt has three sections:
      1. System instructions — role and strict rules for the model
      2. Retrieved context — the relevant chunks from ChromaDB
      3. The user's question

    Args:
        context_chunks: List of retrieved text chunks (strings)
        question:       The user's question

    Returns:
        Complete prompt string ready to send to Gemini
    """
    # Format chunks with numbered labels for clarity
    formatted_chunks = "\n\n".join(
        f"[Source {i + 1}]\n{chunk}"
        for i, chunk in enumerate(context_chunks)
    )

    prompt = f"""You are a helpful AI assistant that answers questions about the webpage the user is currently reading.

STRICT RULES YOU MUST FOLLOW:
1. Answer ONLY using the information provided in the PAGE CONTEXT section below.
2. Do NOT use any external knowledge, training data, or information outside the provided context.
3. If the answer is not present in the context, respond with:
   "I couldn't find that specific information on this page. Try asking something else about the content here."
4. Be concise, clear, and helpful.
5. If the context contains relevant information, give a complete answer — don't be overly brief.
6. You may use markdown formatting (bold, bullet points, code blocks) when it improves clarity.

--- PAGE CONTEXT START ---
{formatted_chunks}
--- PAGE CONTEXT END ---

User Question: {question}

Answer:"""

    return prompt


# ---------------------------------------------------------------------------
# Main generate function — called by chat_service.py
# ---------------------------------------------------------------------------

def generate_answer(context_chunks: list[str], question: str) -> str:
    """
    Sends the RAG prompt to Gemini and returns the generated answer.

    Args:
        context_chunks: Retrieved text chunks from ChromaDB (already ranked by relevance)
        question:       The user's question

    Returns:
        Gemini's answer as a string.

    Raises:
        ValueError: If API key is missing
        Exception:  If Gemini API call fails
    """
    model = _get_model()
    prompt = _build_rag_prompt(context_chunks, question)

    logger.info(
        f"Sending prompt to Gemini | "
        f"chunks={len(context_chunks)} | "
        f"question='{question[:60]}...'"
    )

    try:
        response = model.generate_content(prompt)

        # Safety check — Gemini may block responses that trigger safety filters
        if not response.text:
            logger.warning("Gemini returned an empty response (possibly safety-filtered)")
            return (
                "I wasn't able to generate a response for that question. "
                "Please try rephrasing it."
            )

        answer = response.text.strip()
        logger.info(f"Gemini response received ({len(answer)} chars)")
        return answer

    except Exception as e:
        logger.error(f"Gemini API error: {e}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Streaming generate function — called by chat_stream endpoint (Phase 8)
# ---------------------------------------------------------------------------

from typing import Generator


def generate_answer_stream(
    context_chunks: list[str],
    question: str,
) -> Generator[str, None, None]:
    """
    Streams the Gemini response chunk-by-chunk rather than waiting for
    the full answer.

    --- WHY STREAMING? ---

    The standard generate_answer() blocks until Gemini finishes the
    complete response (can be 2-5 seconds). With streaming:
      - Gemini sends each word/sentence as soon as it's ready
      - The backend forwards each chunk via SSE (Server-Sent Events)
      - The React UI appends each chunk to the message bubble in real-time
      - The user reads the answer as it appears, like a human typing

    --- HOW GEMINI STREAMING WORKS ---

    model.generate_content(prompt, stream=True) returns an iterable.
    Each iteration yields a response chunk with a .text attribute.
    We simply yield each non-empty .text to our caller.

    Args:
        context_chunks: Retrieved text chunks from ChromaDB (same as generate_answer)
        question:       The user's question

    Yields:
        String text chunks from Gemini as they arrive (word or sentence fragments)

    Raises:
        ValueError: If API key is missing
        Exception:  If Gemini API call fails
    """
    model = _get_model()
    prompt = _build_rag_prompt(context_chunks, question)

    logger.info(
        f"Starting Gemini stream | "
        f"chunks={len(context_chunks)} | "
        f"question='{question[:60]}...'"
    )

    try:
        response = model.generate_content(prompt, stream=True)

        for chunk in response:
            if chunk.text:
                yield chunk.text

        logger.info("Gemini stream completed successfully")

    except Exception as e:
        logger.error(f"Gemini streaming error: {e}", exc_info=True)
        raise
