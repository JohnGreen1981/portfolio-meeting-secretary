# Meeting Secretary

## Purpose

Sanitized portfolio repository for a Telegram bot that transcribes meeting recordings and returns structured summaries.

This repo is intended for public review. It must stay free of private recordings, transcripts, logs, tokens, VPS credentials and speaker names from real meetings.

## Stack

- Python 3.11
- aiogram 3
- httpx
- AssemblyAI Speech-to-Text
- OpenAI API for optional speaker mapping and summary generation
- Docker / Docker Compose
- Telegram Local Bot API for large-file handling

## Structure

```text
main.py                         entrypoint
meeting_secretary/bot.py        Telegram handlers and processing workflow
meeting_secretary/config.py     settings loader
meeting_secretary/transcription.py
meeting_secretary/speaker_mapping.py
meeting_secretary/meeting_summary.py
meeting_secretary/media_metadata.py
docs/local-bot-api.md
```

## AI-Assisted Development Note

This project is presented as an AI-assisted automation prototype. The portfolio emphasis is workflow design, prompt/control decisions, API integration, file-size constraints, manual scenario checks and documentation.

Do not describe it as a hand-written production backend.

## Rules

- Do not commit `.env`, `.env.vps`, tokens, recordings, transcripts, logs or private meeting data.
- Keep `.env.example` and `.env.vps.example` placeholder-only.
- If changing runtime code, run `python3 -m py_compile main.py meeting_secretary/*.py`.
- Use synthetic/public-domain demo data only.
- Important summaries should be checked against the transcript.

