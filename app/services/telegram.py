import html
import re

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import Settings


def format_telegram_html(text: str) -> str:
    """Convert Echo's lightweight Markdown into Telegram-safe HTML.

    Telegram has no table layout, so Markdown table rows become compact bullets.
    All model-generated HTML is escaped before supported formatting is added.
    """
    output: list[str] = []
    in_table = False

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                in_table = True
                continue
            escaped_cells = [_format_inline(cell) for cell in cells]
            if not in_table:
                output.append("<b>" + " · ".join(_strip_bold(cell) for cell in escaped_cells) + "</b>")
                in_table = True
            elif escaped_cells:
                first, *rest = escaped_cells
                detail = " · ".join(rest)
                output.append(f"• {first}" + (f"\n  {detail}" if detail else ""))
            continue

        in_table = False
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            output.append(f"<b>{_format_inline(heading.group(1))}</b>")
        elif re.match(r"^[-*]\s+", line):
            output.append("• " + _format_inline(re.sub(r"^[-*]\s+", "", line)))
        else:
            output.append(_format_inline(line))

    return "\n".join(output)


def _format_inline(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", escaped)
    return escaped


def _strip_bold(value: str) -> str:
    return value.removeprefix("<b>").removesuffix("</b>")


class TelegramBridge:
    """Telegram is an interface: it delegates all intelligence to /chat."""

    def __init__(self, settings: Settings, api_base_url: str | None = None) -> None:
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required to start the Telegram bridge")
        self.settings = settings
        self.api_base_url = (api_base_url or settings.echo_api_base_url).rstrip("/")

    def build_application(self) -> Application:
        application = Application.builder().token(self.settings.telegram_bot_token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        return application

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message:
            await update.message.reply_text("Echo is awake.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if not update.message or not update.message.text:
            return
        loading_message = await update.message.reply_text("Thinking...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
                response = await client.post(f"{self.api_base_url}/chat", json={"message": update.message.text})
                response.raise_for_status()
        except httpx.ConnectError:
            await loading_message.edit_text(
                f"Echo API is not reachable at {self.api_base_url}. Start it with: uvicorn app.main:app --reload"
            )
            return
        except httpx.ReadTimeout:
            await loading_message.edit_text(
                "Echo is taking too long to answer. The model or another external API may be slow."
            )
            return
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            await loading_message.edit_text(f"Echo API returned HTTP {exc.response.status_code}: {body}")
            return
        except httpx.HTTPError as exc:
            detail = str(exc) or exc.__class__.__name__
            await loading_message.edit_text(f"Echo API request failed: {detail}")
            return

        formatted = format_telegram_html(response.json()["response"])
        await loading_message.edit_text(formatted, parse_mode=ParseMode.HTML)
