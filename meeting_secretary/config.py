"""Configuration helpers for the meeting secretary bot."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or value.strip() == "":
        return default
    items = tuple(part.strip() for part in value.split(",") if part.strip())
    return items or default


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    assemblyai_api_key: str
    openai_api_key: str | None
    owner_id: int
    max_input_mb: int
    telegram_bot_api_base_url: str | None
    telegram_bot_api_local_mode: bool
    assemblyai_base_url: str
    assemblyai_language_code: str | None
    assemblyai_speech_models: tuple[str, ...]
    assemblyai_min_speakers: int | None
    assemblyai_max_speakers: int | None
    assemblyai_speaker_identification_type: str | None
    assemblyai_speaker_identification_values: tuple[str, ...]
    assemblyai_poll_interval_seconds: float
    assemblyai_timeout_seconds: int
    openai_base_url: str
    openai_speaker_mapping_model: str
    openai_meeting_summary_model: str
    openai_speaker_mapping_confidence_threshold: float
    openai_timeout_seconds: int
    app_build: str

    @property
    def max_input_bytes(self) -> int:
        return self.max_input_mb * 1024 * 1024

    @property
    def telegram_cloud_download_limit_bytes(self) -> int | None:
        if self.telegram_bot_api_local_mode:
            return None
        return 20 * 1024 * 1024

    @property
    def telegram_api_mode_label(self) -> str:
        if self.telegram_bot_api_local_mode:
            return "local"
        if self.telegram_bot_api_base_url:
            return "custom"
        return "cloud"


def load_settings() -> Settings:
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None

    missing = []
    if not telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not assemblyai_api_key:
        missing.append("ASSEMBLYAI_API_KEY")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {joined}")

    owner_id = _parse_optional_int(os.getenv("OWNER_ID")) or 0
    max_input_mb = int(os.getenv("MAX_INPUT_MB", "200"))
    telegram_bot_api_base_url = os.getenv("TELEGRAM_BOT_API_BASE_URL", "").strip() or None
    telegram_bot_api_local_mode = _parse_bool(os.getenv("TELEGRAM_BOT_API_LOCAL_MODE"), default=False)
    assemblyai_base_url = os.getenv("ASSEMBLYAI_BASE_URL", "https://api.assemblyai.com").strip().rstrip("/")
    assemblyai_language_code = os.getenv("ASSEMBLYAI_LANGUAGE_CODE", "ru").strip() or None
    assemblyai_speech_models = _parse_csv(os.getenv("ASSEMBLYAI_SPEECH_MODELS"), ("universal-2",))
    assemblyai_min_speakers = _parse_optional_int(os.getenv("ASSEMBLYAI_MIN_SPEAKERS"))
    assemblyai_max_speakers = _parse_optional_int(os.getenv("ASSEMBLYAI_MAX_SPEAKERS"))
    speaker_identification_type = os.getenv("ASSEMBLYAI_SPEAKER_IDENTIFICATION_TYPE", "").strip().lower() or None
    if speaker_identification_type not in {None, "name", "role"}:
        raise ValueError("ASSEMBLYAI_SPEAKER_IDENTIFICATION_TYPE must be 'name' or 'role'")
    speaker_identification_values = _parse_csv(os.getenv("ASSEMBLYAI_SPEAKER_IDENTIFICATION_VALUES"), ())
    assemblyai_poll_interval_seconds = float(os.getenv("ASSEMBLYAI_POLL_INTERVAL_SECONDS", "3"))
    assemblyai_timeout_seconds = int(os.getenv("ASSEMBLYAI_TIMEOUT_SECONDS", "3600"))
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").strip().rstrip("/")
    openai_speaker_mapping_model = os.getenv("OPENAI_SPEAKER_MAPPING_MODEL", "gpt-5-nano").strip() or "gpt-5-nano"
    openai_meeting_summary_model = os.getenv("OPENAI_MEETING_SUMMARY_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
    openai_speaker_mapping_confidence_threshold = float(
        os.getenv("OPENAI_SPEAKER_MAPPING_CONFIDENCE_THRESHOLD", "0.7")
    )
    openai_timeout_seconds = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
    app_build = os.getenv("APP_BUILD", "dev").strip() or "dev"

    return Settings(
        telegram_bot_token=telegram_bot_token,
        assemblyai_api_key=assemblyai_api_key,
        openai_api_key=openai_api_key,
        owner_id=owner_id,
        max_input_mb=max_input_mb,
        telegram_bot_api_base_url=telegram_bot_api_base_url,
        telegram_bot_api_local_mode=telegram_bot_api_local_mode,
        assemblyai_base_url=assemblyai_base_url,
        assemblyai_language_code=assemblyai_language_code,
        assemblyai_speech_models=assemblyai_speech_models,
        assemblyai_min_speakers=assemblyai_min_speakers,
        assemblyai_max_speakers=assemblyai_max_speakers,
        assemblyai_speaker_identification_type=speaker_identification_type,
        assemblyai_speaker_identification_values=speaker_identification_values,
        assemblyai_poll_interval_seconds=assemblyai_poll_interval_seconds,
        assemblyai_timeout_seconds=assemblyai_timeout_seconds,
        openai_base_url=openai_base_url,
        openai_speaker_mapping_model=openai_speaker_mapping_model,
        openai_meeting_summary_model=openai_meeting_summary_model,
        openai_speaker_mapping_confidence_threshold=openai_speaker_mapping_confidence_threshold,
        openai_timeout_seconds=openai_timeout_seconds,
        app_build=app_build,
    )
