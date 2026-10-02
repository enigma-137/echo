# Echo Setup And Keys

## Minimum Local Setup

1. Install Python 3.12 or newer.
2. Create and activate a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env`.
5. Run `uvicorn app.main:app --reload`.

## Minimal No-Key Test

Set:

```env
MODEL_PROVIDER=mock
DATABASE_URL=sqlite+aiosqlite:///./data/echo.db
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"Hello\"}"
```

## Gemini Test Setup

Needed:

- Google AI Studio account
- Gemini API key

Set:

```env
MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-flash-lite-latest
```

Gemini is isolated to `app/providers/gemini.py`. Replacing Gemini later means adding another provider, not rewriting the agent.

## Telegram Setup

Needed:

- Telegram account
- BotFather bot token

Set:

```env
TELEGRAM_BOT_TOKEN=your_token_here
```

Run:

```bash
uvicorn app.main:app --reload
python -m app.run_telegram
```

Telegram sends every message to the REST `/chat` endpoint. It does not contain agent logic.

## Open-Meteo Weather Setup

No account, payment method, or API key is required for personal/non-commercial use. Optional endpoint overrides:

```env
OPEN_METEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast
OPEN_METEO_GEOCODING_URL=https://geocoding-api.open-meteo.com/v1/search
```

The weather tool supports:

- Current weather
- Today's forecast
- 7-day forecast
- Rain probability
- Temperature
- Humidity
- Wind
- UV Index

It returns structured JSON to the agent, not formatted prose.

## Google Calendar Setup

Echo uses Google's official Calendar API through `google-api-python-client`.

### Option A: OAuth User Consent

Use this for your personal calendar.

Needed in Google Cloud:

- A Google Cloud project
- Google Calendar API enabled
- OAuth consent screen configured
- OAuth 2.0 Client ID, type `Desktop app`
- Downloaded OAuth client secret JSON

Set:

```env
GOOGLE_CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_CLIENT_SECRETS_FILE=path/to/oauth-client-secret.json
GOOGLE_CALENDAR_TOKEN_FILE=data/google-calendar-token.json
```

Generate the local OAuth token:

```bash
python scripts/google_calendar_oauth.py
```

The token is stored at `GOOGLE_CALENDAR_TOKEN_FILE`. Keep it out of git.

### Option B: Service Account

Use this if you want server-to-server access. For a personal Gmail calendar, share the target calendar with the service-account email first. For Google Workspace, you can also configure domain-wide delegation.

Needed in Google Cloud:

- Google Calendar API enabled
- Service account
- Service-account key JSON
- Calendar shared with the service-account email, unless using Workspace delegation

Set:

```env
GOOGLE_CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_ID=your-email@gmail.com
GOOGLE_CALENDAR_CREDENTIALS_FILE=path/to/service-account-key.json
GOOGLE_CALENDAR_SERVICE_ACCOUNT_SUBJECT=
```

If you use Workspace domain-wide delegation, set `GOOGLE_CALENDAR_SERVICE_ACCOUNT_SUBJECT` to the impersonated user email.

## Production Database

Local development uses SQLite:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/echo.db
```

For PostgreSQL, install `asyncpg` and use:

```env
DATABASE_URL=postgresql+asyncpg://echo:password@localhost:5432/echo
```

## Optional Integrations To Choose Later

- Weather: OpenWeather, WeatherAPI, Open-Meteo, Tomorrow.io, or similar.
- Calendar: Google Calendar, Outlook Calendar, CalDAV, or local calendar store.
- Voice: Whisper/OpenAI, Deepgram, AssemblyAI, or local STT.
- Robot: serial, ROS, MQTT, WebSocket, or HTTP control adapter.
- Notifications: Telegram now, then WhatsApp, Slack, Discord, email.

## Files To Edit When Extending

- New model provider: `app/providers/`
- Provider selection: `app/providers/factory.py`
- New tool: `app/tools/`
- Tool registration: `app/tools/__init__.py`
- Persistent storage: `app/models/` and Alembic migrations
- Profile facts: `app/memory/profile.py`
