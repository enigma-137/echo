import asyncio
import sys


def configure_runtime() -> None:
    """Apply runtime compatibility settings before async loops start."""

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
