import asyncio
import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailService:
    """Gmail API wrapper for Echo's email tool."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def recent(self, limit: int = 10) -> dict[str, Any]:
        return await self.search("in:anywhere", limit=limit)

    async def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            service = self._service()
            response = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max(1, min(limit, 25)),
            ).execute()
            messages = response.get("messages", [])
            return {
                "provider": "gmail",
                "query": query,
                "messages": [self._message_summary(service, message["id"]) for message in messages],
            }

        return await self._execute(call)

    async def read_message(self, message_id: str) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            message = self._service().users().messages().get(userId="me", id=message_id, format="full").execute()
            return {"provider": "gmail", "message": self._serialize_message(message)}

        return await self._execute(call)

    async def read_thread(self, thread_id: str) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            thread = self._service().users().threads().get(userId="me", id=thread_id, format="full").execute()
            return {
                "provider": "gmail",
                "thread_id": thread.get("id"),
                "messages": [self._serialize_message(message) for message in thread.get("messages", [])],
            }

        return await self._execute(call)

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            draft = self._service().users().drafts().create(
                userId="me",
                body={"message": self._email_payload(to, subject, body, thread_id)},
            ).execute()
            return {
                "provider": "gmail",
                "action": "create_draft",
                "draft_id": draft.get("id"),
                "message": draft.get("message"),
            }

        return await self._execute(call)

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            sent = self._service().users().messages().send(
                userId="me",
                body=self._email_payload(to, subject, body, thread_id),
            ).execute()
            return {"provider": "gmail", "action": "send_email", "message": sent}

        return await self._execute(call)

    async def _execute(self, call) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(call)
        except HttpError as exc:
            return {"provider": "gmail", "ok": False, "error": self._http_error(exc)}
        except FileNotFoundError as exc:
            return {"provider": "gmail", "ok": False, "error": str(exc)}
        except ValueError as exc:
            return {"provider": "gmail", "ok": False, "error": str(exc)}
        except OSError as exc:
            return {"provider": "gmail", "ok": False, "error": f"Gmail connection failed: {exc}"}
        except Exception as exc:
            return {"provider": "gmail", "ok": False, "error": f"Gmail request failed: {exc}"}

    def _service(self):
        return build("gmail", "v1", credentials=self._credentials(), cache_discovery=False)

    def _credentials(self) -> Credentials:
        token_file = Path(self.settings.google_gmail_token_file)
        if token_file.exists():
            credentials = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                token_file.parent.mkdir(parents=True, exist_ok=True)
                token_file.write_text(credentials.to_json(), encoding="utf-8")
            if credentials.valid:
                return credentials

        raise FileNotFoundError(
            "Gmail OAuth token is not configured yet. Run `python scripts/google_gmail_oauth.py` once."
        )

    @staticmethod
    def _message_summary(service, message_id: str) -> dict[str, Any]:
        message = service.users().messages().get(userId="me", id=message_id, format="metadata").execute()
        headers = GmailService._headers(message)
        return {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "snippet": message.get("snippet"),
            "from": headers.get("from"),
            "to": headers.get("to"),
            "subject": headers.get("subject"),
            "date": headers.get("date"),
            "label_ids": message.get("labelIds", []),
        }

    @staticmethod
    def _serialize_message(message: dict[str, Any]) -> dict[str, Any]:
        headers = GmailService._headers(message)
        return {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "snippet": message.get("snippet"),
            "from": headers.get("from"),
            "to": headers.get("to"),
            "subject": headers.get("subject"),
            "date": headers.get("date"),
            "label_ids": message.get("labelIds", []),
            "body_text": GmailService._plain_text_body(message.get("payload", {})),
        }

    @staticmethod
    def _headers(message: dict[str, Any]) -> dict[str, str]:
        payload = message.get("payload", {})
        headers = payload.get("headers", [])
        return {header.get("name", "").lower(): header.get("value", "") for header in headers}

    @staticmethod
    def _plain_text_body(payload: dict[str, Any]) -> str:
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return GmailService._decode_body(payload["body"]["data"])
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return GmailService._decode_body(part["body"]["data"])
            nested = GmailService._plain_text_body(part)
            if nested:
                return nested
        return ""

    @staticmethod
    def _decode_body(value: str) -> str:
        return base64.urlsafe_b64decode(value.encode("utf-8")).decode("utf-8", errors="replace")

    @staticmethod
    def _email_payload(to: str, subject: str, body: str, thread_id: str | None = None) -> dict[str, Any]:
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        payload: dict[str, Any] = {
            "raw": base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8"),
        }
        if thread_id:
            payload["threadId"] = thread_id
        return payload

    @staticmethod
    def _http_error(error: HttpError) -> str:
        try:
            return error.content.decode("utf-8")
        except AttributeError:
            return str(error)
