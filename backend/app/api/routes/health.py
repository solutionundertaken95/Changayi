"""
health.py — The /api/health endpoint.

Why do we need a health endpoint?
  Before the Chrome extension sends any real data, it should confirm
  the backend is alive. This is standard practice in any API-driven product.
  It also gives us an easy first thing to test when setting up the project.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    message: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Returns 200 OK with a simple status message.
    The Chrome extension will hit this before doing anything else.
    """
    return HealthResponse(
        status="ok",
        message="RAG Chatbot backend is running",
        version="0.1.0",
    )
