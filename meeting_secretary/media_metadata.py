"""Media metadata helpers."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path


DATE_TAG_CANDIDATES = (
    "creation_time",
    "com.apple.quicktime.creationdate",
    "date",
    "year",
    "encoded_date",
    "tagged_date",
)


def extract_media_recorded_at(path: Path) -> datetime | None:
    ffprobe = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        proc = subprocess.run(ffprobe, capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None

    for tag_value in iter_candidate_tag_values(payload):
        parsed = parse_media_date(tag_value)
        if parsed is not None:
            return parsed

    return None


def iter_candidate_tag_values(payload: dict) -> list[str]:
    values: list[str] = []
    format_tags = (payload.get("format") or {}).get("tags") or {}
    stream_items = payload.get("streams") or []

    for key in DATE_TAG_CANDIDATES:
        value = format_tags.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())

    for stream in stream_items:
        tags = stream.get("tags") or {}
        for key in DATE_TAG_CANDIDATES:
            value = tags.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())

    return values


def parse_media_date(value: str) -> datetime | None:
    cleaned = value.strip()
    if not cleaned:
        return None

    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    for candidate in (
        cleaned,
        cleaned.replace(" ", "T"),
        cleaned.replace("UTC", "+00:00"),
    ):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            pass

    return None
