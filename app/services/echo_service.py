"""Shared text-generation logic for Echo.

Both `/chat` and `/voice` call :func:`generate_echo_response` so the AI
behavior is defined in exactly one place. The optional ``context`` argument is
reserved for future session/conversation IDs and is unused in V1.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import EchoAgent
from app.config import Settings
from app.providers import get_model_provider

logger = logging.getLogger(__name__)


async def generate_echo_response(
    db: AsyncSession,
    settings: Settings,
    message: str,
    context: str | None = None,
) -> str:
    """Run the Echo agent over ``message`` and return its text response.

    Args:
        db: Open async SQLAlchemy session.
        settings: Application settings (drives provider selection).
        message: The user message to answer.
        context: Reserved for future per-session context (currently unused).
    """
    provider = get_model_provider(settings)
    agent = EchoAgent(db, provider, settings)
    return await agent.chat(message)
