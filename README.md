# Echo

Echo is a modular, self-hosted personal AI assistant with dynamic vector memory, automated fact extraction, tool calling, and speech processing. It exposes one core agent through a REST API, with Telegram and ESP32 voice interfaces.

## What Is Built

- FastAPI app with `/health`, `/chat`, `/memory`, `/profile`, and memory delete/update routes.
- Async SQLAlchemy models for users, memories, conversations, notes, and reminders.
- Dynamic vector memory with FastEmbed semantic retrieval and automated fact extraction.
- Provider-neutral model interface in `app/providers/base.py`.
- Gemini implementation in `app/providers/gemini.py`.
- Groq/Llama implementation in `app/providers/groq_provider.py`.
- Mock provider for local smoke tests without keys.
- Tool registry with weather, calendar, memory, notes, and reminder tools.
- Open-Meteo integration with current weather, forecasts, rain probability, temperature, humidity, wind, and UV index; no API key required for non-commercial use.
- Google Calendar integration behind a provider interface.
- Conversation summaries are stored instead of full transcripts.
- Telegram bridge in `app/services/telegram.py` and `app/run_telegram.py`.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

For a no-key smoke test, set this in `.env`:

```env
MODEL_PROVIDER=mock
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Test it:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"Hello Echo\"}"
```

## ESP32 voice API

`POST /voice` accepts one `multipart/form-data` field named `audio`. V1 accepts
PCM signed 16-bit little-endian WAV recordings; mono 16 kHz input is recommended.
The response body is a WAV file normalized to `AUDIO_SAMPLE_RATE` and
`AUDIO_CHANNELS` (defaults: 16 kHz mono). Short, ASCII-safe debug values may be
returned in `X-Echo-Transcript` and `X-Echo-Response`.

Production example configuration:

```env
STT_PROVIDER=spitch
TTS_PROVIDER=spitch
SPITCH_API_KEY=your-spitch-api-key
SPITCH_STT_LANGUAGE=en
SPITCH_TTS_LANGUAGE=en
SPITCH_TTS_VOICE=lucy
SPITCH_TTS_SPEED=1.0
SPITCH_MAX_RETRIES=2
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
MAX_VOICE_UPLOAD_MB=5
```

Supported Spitch language choices include `en`, `yo`, `ha`, and `ig`. The
voice and STT language can be changed independently without changing the API
contract used by the ESP32.

Install, run, and test locally:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl -X POST http://localhost:8000/voice \
  -F "audio=@sample.wav;type=audio/wav" \
  --output response.wav
python -m unittest discover -s tests -v
```

For an offline wiring check, set `MODEL_PROVIDER=mock`, `STT_PROVIDER=mock`, and
`TTS_PROVIDER=mock`. Mock TTS emits a valid test tone, not spoken words.

Diagnose Gemini locally:

```bash
python scripts/test_gemini.py
```

This checks DNS, TLS, raw REST `generateContent`, and the `google-genai` SDK without printing your full API key.

## Keys You Need

### Required For Groq

`GROQ_API_KEY`

Echo currently works well with Groq-hosted Llama. Set:

```env
MODEL_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### Optional Gemini Provider

Gemini is still available as a swappable provider:

```env
MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-flash-lite-latest
```

### Required For Telegram

`TELEGRAM_BOT_TOKEN`

Create a bot with BotFather in Telegram, then set:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

Start the API first, then in a second terminal:

```bash
python -m app.run_telegram
```

### Open-Meteo Weather

No weather API key is required. Echo uses Open-Meteo's forecast and geocoding endpoints:

```env
OPEN_METEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast
OPEN_METEO_GEOCODING_URL=https://geocoding-api.open-meteo.com/v1/search
```

The weather tool returns structured JSON to the agent.

### Google Calendar

Google Calendar is implemented through `app/services/calendar.py`, so other providers can be added later without changing the agent.

For normal personal-calendar OAuth, create an OAuth 2.0 Client ID in Google Cloud:

1. Enable the Google Calendar API.
2. Create an OAuth consent screen.
3. Create an OAuth Client ID for a Desktop app.
4. Download the client secret JSON.
5. Set:

```env
GOOGLE_CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_CLIENT_SECRETS_FILE=path/to/oauth-client-secret.json
GOOGLE_CALENDAR_TOKEN_FILE=data/google-calendar-token.json
```

Generate the token:

```bash
python scripts/google_calendar_oauth.py
```

For service-account mode, share the target calendar with the service-account email, then set:

```env
GOOGLE_CALENDAR_CREDENTIALS_FILE=path/to/service-account-key.json
GOOGLE_CALENDAR_ID=your_calendar_id_or_email
```

## Environment Variables

| Name | Required | Purpose |
| --- | --- | --- |
| `APP_NAME` | No | API display name. |
| `ENVIRONMENT` | No | `development`, `staging`, or `production`. |
| `DATABASE_URL` | Yes | SQLAlchemy async database URL. Defaults to local SQLite. |
| `MODEL_PROVIDER` | Yes | `groq`, `gemini`, or `mock`. |
| `GROQ_API_KEY` | For Groq | Groq API key. |
| `GROQ_MODEL` | For Groq | Groq model name. |
| `GEMINI_API_KEY` | For Gemini | Google Gemini API key. |
| `GEMINI_MODEL` | For Gemini | Gemini model name. |
| `TELEGRAM_BOT_TOKEN` | For Telegram | Telegram bot token from BotFather. |
| `TELEGRAM_WEBHOOK_URL` | No | Reserved for future webhook mode. |
| `OPEN_METEO_FORECAST_URL` | No | Open-Meteo forecast endpoint. |
| `OPEN_METEO_GEOCODING_URL` | No | Open-Meteo location search endpoint. |
| `GOOGLE_CALENDAR_PROVIDER` | No | Calendar provider, currently `google`. |
| `GOOGLE_CALENDAR_ID` | For calendar | Calendar ID, usually `primary` for OAuth or an email/calendar ID for service accounts. |
| `GOOGLE_CALENDAR_CLIENT_SECRETS_FILE` | For OAuth setup | Google OAuth client secret JSON path. |
| `GOOGLE_CALENDAR_TOKEN_FILE` | For OAuth calendar | Stored OAuth token JSON path. Keep out of git. |
| `GOOGLE_CALENDAR_CREDENTIALS_FILE` | Optional | Service-account credential JSON path. |
| `GOOGLE_CALENDAR_SERVICE_ACCOUNT_SUBJECT` | Optional | Domain-wide delegation subject. |
| `DEFAULT_TIMEZONE` | No | User timezone. |
| `CORS_ORIGINS` | No | JSON list of allowed origins. |

## How Provider Swapping Works

Echo does not call Gemini directly from routes or tools. The agent depends on this interface:

```python
class ModelProvider:
    async def complete_text(...)
    async def plan(...)
    async def respond_with_tool_results(...)
```

To add OpenAI, Anthropic, a local model, or any other provider:

1. Create `app/providers/your_provider.py`.
2. Implement `ModelProvider`.
3. Add it to `app/providers/factory.py`.
4. Set `MODEL_PROVIDER=your_provider`.

No API routes, database models, Telegram code, or tool code should need to change.

## How Tools Work

Every capability is an `EchoTool`:

- `schema()` tells the model what the tool can do.
- `run(arguments)` executes business logic in Python.
- The agent asks the model for a JSON plan.
- Python executes tool calls.
- The model writes the final user-facing answer from tool results.

To add a new capability:

1. Create a new file in `app/tools/`.
2. Subclass `EchoTool`.
3. Register it in `app/tools/__init__.py`.

This is the path for future robot, voice, camera, email, WhatsApp, Slack, Discord, MCP, and home automation tools.

## Current Limitations

- Calendar requires either a generated OAuth token or a service account that has access to the target calendar.
- SQLite is used by default for development. Use PostgreSQL in production.
- The agent uses a JSON planning contract instead of native provider-specific function calling so providers remain easy to swap.
### Gmail

Gmail uses OAuth 2.0 through the official Gmail API.

Set:

```env
GOOGLE_GMAIL_CLIENT_SECRETS_FILE=google-gmail-client-secret.json
GOOGLE_GMAIL_TOKEN_FILE=data/google-gmail-token.json
```

Generate the local token once:

```bash
python scripts/google_gmail_oauth.py
```

Echo can search recent mail, read messages/threads, and create drafts. Sending is guarded and requires explicit confirmation.
