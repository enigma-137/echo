import asyncio

from app.runtime import configure_runtime
from app.config import get_settings
from app.services.telegram import TelegramBridge

configure_runtime()


async def run() -> None:
    bridge = TelegramBridge(get_settings())
    application = bridge.build_application()
    await application.initialize()
    await application.start()
    if not application.updater:
        raise RuntimeError("Telegram updater was not created")
    await application.updater.start_polling()
    print("Echo Telegram bridge is running. Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
