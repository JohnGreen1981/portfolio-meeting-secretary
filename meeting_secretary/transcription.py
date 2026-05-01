"""AssemblyAI transcription client and transcript formatting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx


@dataclass(frozen=True)
class Utterance:
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


@dataclass(frozen=True)
class TranscriptResult:
    transcript_id: str
    text: str
    utterances: tuple[Utterance, ...]
    speech_model_used: str | None


@dataclass(frozen=True)
class SpeakerIdentificationRequest:
    speaker_type: str
    known_values: tuple[str, ...]


class AssemblyAIClient:
    """Small async client for AssemblyAI pre-recorded transcription."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        speech_models: tuple[str, ...],
        language_code: str | None,
        min_speakers: int | None,
        max_speakers: int | None,
        poll_interval_seconds: float,
        timeout_seconds: int,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._speech_models = speech_models
        self._language_code = language_code
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._poll_interval_seconds = poll_interval_seconds
        self._timeout_seconds = timeout_seconds

    async def upload_audio(self, audio_bytes: bytes) -> str:
        timeout = httpx.Timeout(connect=30.0, read=120.0, write=120.0, pool=30.0)
        headers = {"authorization": self._api_key}

        async with httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=timeout) as client:
            upload_response = await client.post("/v2/upload", content=audio_bytes)
            upload_response.raise_for_status()
            return upload_response.json()["upload_url"]

    async def submit_transcript(
        self,
        upload_url: str,
        *,
        speaker_identification: SpeakerIdentificationRequest | None = None,
    ) -> str:
        timeout = httpx.Timeout(connect=30.0, read=120.0, write=120.0, pool=30.0)
        headers = {"authorization": self._api_key}

        async with httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=timeout) as client:
            payload: dict[str, object] = {
                "audio_url": upload_url,
                "speech_models": list(self._speech_models),
                "speaker_labels": True,
            }

            if self._language_code:
                payload["language_code"] = self._language_code
            elif len(self._speech_models) > 1:
                payload["language_detection"] = True

            if self._min_speakers is not None and self._max_speakers is not None:
                if self._min_speakers == self._max_speakers:
                    payload["speakers_expected"] = self._min_speakers
                else:
                    payload["speaker_options"] = {
                        "min_speakers_expected": self._min_speakers,
                        "max_speakers_expected": self._max_speakers,
                    }

            if speaker_identification is not None and speaker_identification.known_values:
                payload["speech_understanding"] = {
                    "request": {
                        "speaker_identification": {
                            "speaker_type": speaker_identification.speaker_type,
                            "known_values": list(speaker_identification.known_values),
                        }
                    }
                }

            transcript_response = await client.post("/v2/transcript", json=payload)
            transcript_response.raise_for_status()
            return transcript_response.json()["id"]

    async def wait_for_transcript(self, transcript_id: str) -> TranscriptResult:
        timeout = httpx.Timeout(connect=30.0, read=120.0, write=120.0, pool=30.0)
        headers = {"authorization": self._api_key}

        async with httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=timeout) as client:
            deadline = asyncio.get_running_loop().time() + self._timeout_seconds
            while True:
                if asyncio.get_running_loop().time() > deadline:
                    raise TimeoutError(
                        f"AssemblyAI transcription timed out after {self._timeout_seconds} seconds "
                        f"(transcript_id={transcript_id})"
                    )

                poll_response = await client.get(f"/v2/transcript/{transcript_id}")
                poll_response.raise_for_status()
                data = poll_response.json()
                status = data.get("status")

                if status == "completed":
                    return TranscriptResult(
                        transcript_id=transcript_id,
                        text=data.get("text") or "",
                        utterances=tuple(
                            Utterance(
                                speaker=item.get("speaker") or "?",
                                text=item.get("text") or "",
                                start_ms=int(item.get("start") or 0),
                                end_ms=int(item.get("end") or 0),
                                confidence=item.get("confidence"),
                            )
                            for item in data.get("utterances") or []
                        ),
                        speech_model_used=data.get("speech_model_used"),
                    )

                if status == "error":
                    raise RuntimeError(f"AssemblyAI transcription failed: {data.get('error') or 'unknown error'}")

                await asyncio.sleep(self._poll_interval_seconds)

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        speaker_identification: SpeakerIdentificationRequest | None = None,
    ) -> TranscriptResult:
        upload_url = await self.upload_audio(audio_bytes)
        transcript_id = await self.submit_transcript(
            upload_url,
            speaker_identification=speaker_identification,
        )
        return await self.wait_for_transcript(transcript_id)


def build_transcript_text(result: TranscriptResult, *, source_name: str | None) -> str:
    lines = [
        "Стенограмма встречи",
        f"Сформировано: {datetime.now(UTC).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"Transcript ID: {result.transcript_id}",
    ]

    if source_name:
        lines.append(f"Источник: {source_name}")
    if result.speech_model_used:
        lines.append(f"Модель: {result.speech_model_used}")

    if result.utterances:
        lines.extend(["", "Разбивка по спикерам", ""])
        for utterance in result.utterances:
            speaker_label = format_speaker_label(utterance.speaker)
            lines.append(
                f"[{format_timestamp(utterance.start_ms)} - {format_timestamp(utterance.end_ms)}] "
                f"{speaker_label}: {utterance.text.strip()}"
            )
    else:
        lines.extend(["", "Текст", ""])
        if result.text:
            lines.append(result.text.strip())
        else:
            lines.append("[пустой результат]")

    return "\n".join(lines).strip() + "\n"


def build_transcript_filename(source_name: str | None) -> str:
    stem = Path(source_name or "transcript").stem
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem)
    cleaned = cleaned.strip("_") or "transcript"
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{cleaned}_{timestamp}_transcript.txt"


def summarize_transcript(result: TranscriptResult) -> str:
    return "✅ Готово. Полная стенограмма встречи во вложении."


def format_timestamp(milliseconds: int) -> str:
    seconds = max(milliseconds, 0) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


def format_speaker_label(raw_speaker: str) -> str:
    speaker = (raw_speaker or "?").strip()
    if len(speaker) == 1 and speaker.isalpha():
        return f"Спикер {speaker}"
    return speaker
