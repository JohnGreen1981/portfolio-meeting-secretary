"""Optional GPT-based speaker remapping for transcript utterances."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

import httpx

from meeting_secretary.transcription import TranscriptResult, Utterance


@dataclass(frozen=True)
class SpeakerMappingHint:
    speaker_type: str
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpeakerAlias:
    source_label: str
    target_label: str
    confidence: float
    reasoning: str


class OpenAISpeakerMapper:
    """Use a cheap GPT model to remap diarized speakers to known names or roles."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        confidence_threshold: float,
        timeout_seconds: int,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._confidence_threshold = confidence_threshold
        self._timeout_seconds = timeout_seconds

    async def remap(
        self,
        result: TranscriptResult,
        *,
        hint: SpeakerMappingHint,
    ) -> TranscriptResult:
        if len(result.utterances) < 2:
            return result

        distinct_labels = tuple(dict.fromkeys(item.speaker for item in result.utterances))
        if len(distinct_labels) < 2:
            return result

        aliases = await self._request_aliases(result, hint, distinct_labels)
        filtered: dict[str, str] = {}
        for alias in aliases:
            if alias.confidence < self._confidence_threshold:
                continue
            if alias.source_label not in distinct_labels:
                continue
            if hint.candidates:
                if alias.target_label not in hint.candidates:
                    continue
                filtered[alias.source_label] = alias.target_label
                continue

            cleaned = alias.target_label.strip()
            if not cleaned or cleaned.lower() == alias.source_label.lower():
                continue
            filtered[alias.source_label] = cleaned

        if not filtered:
            return result

        remapped = tuple(
            replace(utterance, speaker=filtered.get(utterance.speaker, utterance.speaker))
            for utterance in result.utterances
        )
        return replace(result, utterances=remapped)

    async def _request_aliases(
        self,
        result: TranscriptResult,
        hint: SpeakerMappingHint,
        distinct_labels: tuple[str, ...],
    ) -> tuple[SpeakerAlias, ...]:
        timeout = httpx.Timeout(connect=15.0, read=float(self._timeout_seconds), write=30.0, pool=15.0)
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You map diarized speaker labels from a meeting transcript to known names or roles. "
                        "Return only valid JSON matching the provided schema. "
                        "Do not guess aggressively: if uncertain, keep the original speaker label as target_label "
                        "and set low confidence. "
                        "When no known candidates are provided, use only names that are directly grounded in the transcript."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(result, hint, distinct_labels),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "speaker_aliases",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "aliases": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "source_label": {"type": "string"},
                                        "target_label": {"type": "string"},
                                        "confidence": {"type": "number"},
                                        "reasoning": {"type": "string"},
                                    },
                                    "required": [
                                        "source_label",
                                        "target_label",
                                        "confidence",
                                        "reasoning",
                                    ],
                                },
                            }
                        },
                        "required": ["aliases"],
                    },
                },
            },
        }

        async with httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=timeout) as client:
            response = await client.post("/v1/chat/completions", json=body)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return tuple(
            SpeakerAlias(
                source_label=item["source_label"],
                target_label=item["target_label"],
                confidence=float(item["confidence"]),
                reasoning=item["reasoning"],
            )
            for item in parsed.get("aliases", [])
        )

    def _build_prompt(
        self,
        result: TranscriptResult,
        hint: SpeakerMappingHint,
        distinct_labels: tuple[str, ...],
    ) -> str:
        transcript_excerpt = []
        for utterance in result.utterances[:80]:
            transcript_excerpt.append(f"{utterance.speaker}: {utterance.text.strip()}")

        if hint.candidates:
            target_instruction = (
                f"Known speaker type: {hint.speaker_type}\n"
                f"Known candidates: {', '.join(hint.candidates)}\n"
                "Return one alias object per diarized label. "
                "If you cannot confidently map a label to one of the known candidates, "
                "keep target_label equal to source_label and set confidence below 0.7."
            )
        else:
            target_instruction = (
                "No known speaker list was provided.\n"
                "Infer speaker labels from the transcript itself.\n"
                "If a real first name is directly supported by the conversation, for example through "
                "self-introduction, direct address, or explicit mention, you may use it.\n"
                "If a likely role is also clear, combine them in one short label like "
                "`Кирилл (клиент)` or `Иван (подрядчик)`.\n"
                "If the name is not reliable, use only a likely role and make it tentative, for example "
                "`возможно: клиент` or `возможно: менеджер`.\n"
                "Do not invent names that are not grounded in the transcript. "
                "If uncertain, keep target_label equal to source_label and set confidence below 0.7."
            )

        return (
            f"Speaker mapping mode: {hint.speaker_type}\n"
            f"Diarized labels: {', '.join(distinct_labels)}\n\n"
            "Transcript excerpt:\n"
            + "\n".join(transcript_excerpt)
            + "\n\n"
            + target_instruction
        )
