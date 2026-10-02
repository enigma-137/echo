from pathlib import Path
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.services.gmail import GMAIL_SCOPES


def main() -> None:
    settings = get_settings()
    if not settings.google_gmail_client_secrets_file:
        raise RuntimeError("Set GOOGLE_GMAIL_CLIENT_SECRETS_FILE in .env first.")

    flow = InstalledAppFlow.from_client_secrets_file(
        settings.google_gmail_client_secrets_file,
        scopes=GMAIL_SCOPES,
    )
    credentials = flow.run_local_server(port=0)
    token_path = Path(settings.google_gmail_token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Saved Gmail OAuth token to {token_path}")


if __name__ == "__main__":
    main()