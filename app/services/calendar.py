import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings


CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarProvider(ABC):
    """Provider-neutral calendar contract for Echo tools."""

    @abstractmethod
    async def today(self) -> dict[str, Any]:
        """Return today's schedule."""

    @abstractmethod
    async def upcoming(self, days: int = 7, limit: int = 20) -> dict[str, Any]:
        """Return upcoming events."""

    @abstractmethod
    async def search(self, query: str, days: int = 30, limit: int = 10) -> dict[str, Any]:
        """Search future events."""

    @abstractmethod
    async def create_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Create an event."""

    @abstractmethod
    async def update_event(self, event_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Update an event."""

    @abstractmethod
    async def delete_event(self, event_id: str) -> dict[str, Any]:
        """Delete an event."""


class GoogleCalendarService(CalendarProvider):
    """Google Calendar implementation using OAuth credentials."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calendar_id = settings.google_calendar_id
        self.timezone = ZoneInfo(settings.default_timezone)

    async def today(self) -> dict[str, Any]:
        start = datetime.combine(datetime.now(self.timezone).date(), time.min, tzinfo=self.timezone)
        end = start + timedelta(days=1)
        return await self._list_events(start, end, limit=50)

    async def upcoming(self, days: int = 7, limit: int = 20) -> dict[str, Any]:
        now = datetime.now(self.timezone)
        end = now + timedelta(days=max(1, min(days, 60)))
        return await self._list_events(now, end, limit=limit)

    async def search(self, query: str, days: int = 30, limit: int = 10) -> dict[str, Any]:
        now = datetime.now(self.timezone)
        end = now + timedelta(days=max(1, min(days, 365)))
        return await self._list_events(now, end, limit=limit, query=query)

    async def create_event(self, event: dict[str, Any]) -> dict[str, Any]:
        body = self._event_body(event)

        def call() -> dict[str, Any]:
            created = self._service().events().insert(calendarId=self.calendar_id, body=body).execute()
            return {"provider": "google", "action": "create", "event": self._serialize_event(created)}

        return await self._execute(call)

    async def update_event(self, event_id: str, event: dict[str, Any]) -> dict[str, Any]:
        body = self._event_body(event, partial=True)

        def call() -> dict[str, Any]:
            updated = self._service().events().patch(calendarId=self.calendar_id, eventId=event_id, body=body).execute()
            return {"provider": "google", "action": "update", "event": self._serialize_event(updated)}

        return await self._execute(call)

    async def delete_event(self, event_id: str) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            self._service().events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            return {"provider": "google", "action": "delete", "event_id": event_id, "deleted": True}

        return await self._execute(call)

    async def _list_events(
        self,
        start: datetime,
        end: datetime,
        limit: int,
        query: str | None = None,
    ) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            request = self._service().events().list(
                calendarId=self.calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                maxResults=max(1, min(limit, 100)),
                singleEvents=True,
                orderBy="startTime",
                q=query,
            )
            events = request.execute().get("items", [])
            now = datetime.now(self.timezone)
            return {
                "provider": "google",
                "calendar_id": self.calendar_id,
                "current_time": now.isoformat(),
                "timezone": str(self.timezone),
                "time_min": start.isoformat(),
                "time_max": end.isoformat(),
                "query": query,
                "events": [self._serialize_event(event, now, self.timezone) for event in events],
            }

        return await self._execute(call)

    async def _execute(self, call) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(call)
        except HttpError as exc:
            return {
                "provider": "google",
                "ok": False,
                "error": self._http_error(exc),
            }
        except FileNotFoundError as exc:
            return {"provider": "google", "ok": False, "error": str(exc)}
        except ValueError as exc:
            return {"provider": "google", "ok": False, "error": str(exc)}
        except OSError as exc:
            return {"provider": "google", "ok": False, "error": f"Google Calendar connection failed: {exc}"}
        except Exception as exc:
            return {"provider": "google", "ok": False, "error": f"Google Calendar request failed: {exc}"}

    def _service(self):
        return build("calendar", "v3", credentials=self._credentials(), cache_discovery=False)

    def _credentials(self):
        token_file = Path(self.settings.google_calendar_token_file)
        if token_file.exists():
            credentials = Credentials.from_authorized_user_file(str(token_file), CALENDAR_SCOPES)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                token_file.parent.mkdir(parents=True, exist_ok=True)
                token_file.write_text(credentials.to_json(), encoding="utf-8")
            if credentials.valid:
                return credentials

        if self.settings.google_calendar_credentials_file:
            credentials_path = Path(self.settings.google_calendar_credentials_file)
            credentials = service_account.Credentials.from_service_account_file(
                str(credentials_path),
                scopes=CALENDAR_SCOPES,
            )
            if self.settings.google_calendar_service_account_subject:
                credentials = credentials.with_subject(self.settings.google_calendar_service_account_subject)
            return credentials

        raise FileNotFoundError(
            "Google Calendar credentials are not configured. Set GOOGLE_CALENDAR_TOKEN_FILE for OAuth user tokens "
            "or GOOGLE_CALENDAR_CREDENTIALS_FILE for service-account credentials."
        )

    def _event_body(self, event: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if title := event.get("title"):
            body["summary"] = title
        if description := event.get("description"):
            body["description"] = description
        if location := event.get("location"):
            body["location"] = location

        starts_at = event.get("starts_at") or event.get("start")
        ends_at = event.get("ends_at") or event.get("end")
        timezone = event.get("timezone") or self.settings.default_timezone
        if starts_at:
            body["start"] = self._time_body(starts_at, timezone)
        if ends_at:
            body["end"] = self._time_body(ends_at, timezone)

        if not partial and ("summary" not in body or "start" not in body or "end" not in body):
            raise ValueError("title, starts_at, and ends_at are required to create a calendar event")
        return body

    @staticmethod
    def _time_body(value: str, timezone: str) -> dict[str, str]:
        if len(value) == 10:
            return {"date": value}
        return {"dateTime": value, "timeZone": timezone}

    @classmethod
    def _serialize_event(cls, event: dict[str, Any], now: datetime | None = None, timezone: ZoneInfo | None = None) -> dict[str, Any]:
        start = event.get("start", {})
        parsed_start = cls._parse_event_time(start, timezone)
        time_until = cls._time_until_payload(parsed_start, now) if parsed_start and now else None
        return {
            "id": event.get("id"),
            "title": event.get("summary"),
            "description": event.get("description"),
            "location": event.get("location"),
            "status": event.get("status"),
            "html_link": event.get("htmlLink"),
            "start": event.get("start"),
            "end": event.get("end"),
            "starts_at": parsed_start.isoformat() if parsed_start else None,
            "time_until": time_until,
            "created": event.get("created"),
            "updated": event.get("updated"),
            "attendees": [
                {
                    "email": attendee.get("email"),
                    "display_name": attendee.get("displayName"),
                    "response_status": attendee.get("responseStatus"),
                }
                for attendee in event.get("attendees", [])
            ],
        }

    @staticmethod
    def _parse_event_time(value: dict[str, Any], timezone: ZoneInfo | None) -> datetime | None:
        raw_value = value.get("dateTime") or value.get("date")
        if not raw_value:
            return None
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone)
        return parsed

    @staticmethod
    def _time_until_payload(event_time: datetime, now: datetime) -> dict[str, Any]:
        delta_seconds = int((event_time - now).total_seconds())
        abs_seconds = abs(delta_seconds)
        hours, remainder = divmod(abs_seconds, 3600)
        minutes = remainder // 60
        if hours and minutes:
            human = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        elif hours:
            human = f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            human = f"{minutes} minute{'s' if minutes != 1 else ''}"
        return {
            "seconds": delta_seconds,
            "minutes": round(delta_seconds / 60, 1),
            "human": human,
            "status": "future" if delta_seconds >= 0 else "past",
        }

    @staticmethod
    def _http_error(error: HttpError) -> str:
        try:
            payload = json.loads(error.content.decode("utf-8"))
            return payload.get("error", {}).get("message") or str(error)
        except (ValueError, AttributeError):
            return str(error)


def get_calendar_provider(settings: Settings) -> CalendarProvider:
    provider = settings.google_calendar_provider.lower()
    if provider == "google":
        return GoogleCalendarService(settings)
    raise ValueError(f"Unsupported calendar provider: {settings.google_calendar_provider}")
