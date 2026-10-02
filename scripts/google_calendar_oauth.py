from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import get_settings
from app.services.calendar import CALENDAR_SCOPES


def main() -> None:
    settings = get_settings()
    if not settings.google_calendar_client_secrets_file:
        raise RuntimeError("Set GOOGLE_CALENDAR_CLIENT_SECRETS_FILE in .env first.")

    flow = InstalledAppFlow.from_client_secrets_file(
        settings.google_calendar_client_secrets_file,
        scopes=CALENDAR_SCOPES,
    )
    credentials = flow.run_local_server(port=0)
    token_path = Path(settings.google_calendar_token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Saved Google Calendar OAuth token to {token_path}")


if __name__ == "__main__":
    main()
