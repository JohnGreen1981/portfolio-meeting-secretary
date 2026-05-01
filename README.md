# Meeting Secretary

Telegram bot for transcribing meetings and generating structured summaries.

This is a sanitized portfolio version. It does not include production `.env` files, meeting recordings, private transcripts, logs, speaker names from real meetings, or VPS credentials.

## What It Demonstrates

- Speech-to-text workflow for long audio/video files.
- Speaker diarization and speaker mapping.
- Chunked summary pipeline for long transcripts.
- Telegram Local Bot API design for files larger than the cloud Bot API limit.
- Docker deployment and runtime verification.
- AI-assisted development workflow: requirements, implementation via coding assistants, manual scenario checks, cleanup and documentation.

## User Workflow

1. User sends a meeting recording to the Telegram bot.
2. Bot validates the file type and size.
3. Bot uploads audio/video to AssemblyAI and waits for diarized transcription.
4. Bot optionally uses GPT to infer speaker names or roles from transcript context.
5. Bot optionally builds a structured meeting summary.
6. User receives a `.txt` transcript file and a concise summary message.

## Stack

- Python 3.11
- aiogram 3
- httpx
- AssemblyAI Speech-to-Text API
- OpenAI API for speaker mapping and summaries
- Docker / Docker Compose
- Telegram Local Bot API for large-file transport

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Required environment variables:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
OPENAI_API_KEY=your_openai_api_key_optional
OWNER_ID=your_telegram_user_id
```

`OPENAI_API_KEY` is optional. Without it, the bot can still return transcripts, but GPT speaker mapping and meeting summaries are disabled.

## Docker

Cloud Bot API mode:

```bash
docker build -t meeting-secretary .
docker run -d \
  --name meeting-secretary \
  --restart unless-stopped \
  --env-file .env \
  meeting-secretary
```

Local Bot API mode for files larger than the cloud Bot API download limit:

```bash
cp .env.vps.example .env.vps
docker compose up -d --build
```

See [docs/local-bot-api.md](docs/local-bot-api.md).

## Project Structure

```text
main.py                         entrypoint
meeting_secretary/bot.py        Telegram handlers and processing workflow
meeting_secretary/config.py     environment settings
meeting_secretary/transcription.py
meeting_secretary/speaker_mapping.py
meeting_secretary/meeting_summary.py
meeting_secretary/media_metadata.py
docs/local-bot-api.md           local Bot API notes
```

## Safety Notes

- Do not commit `.env`, `.env.vps`, real recordings, private transcripts or logs.
- Use synthetic or public-domain demo recordings only.
- Speaker mapping can be uncertain; low-confidence mappings should remain neutral.
- Summaries are convenience outputs and should be checked against the transcript for important decisions.

## Portfolio Note

This project is presented as an AI-assisted automation prototype. The focus is workflow design, prompt/control decisions, large-file constraints, API integration and practical UX, not a claim of hand-written production backend engineering.
