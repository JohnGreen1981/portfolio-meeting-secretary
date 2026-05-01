"""GPT-based meeting summary builder."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from meeting_secretary.transcription import TranscriptResult, format_speaker_label


@dataclass(frozen=True)
class ActionItem:
    owner: str
    task: str
    deadline: str | None


@dataclass(frozen=True)
class MeetingSummary:
    overview: tuple[str, ...]
    decisions: tuple[str, ...]
    action_items: tuple[ActionItem, ...]
    open_questions: tuple[str, ...]
    risks: tuple[str, ...]
    next_step: str | None


@dataclass(frozen=True)
class MeetingSummaryMeta:
    title: str
    meeting_date: str


class OpenAIMeetingSummaryBuilder:
    """Build a concise business summary from a transcript."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def summarize(self, result: TranscriptResult) -> MeetingSummary:
        chunks = split_transcript_into_chunks(result, max_chars=12000)
        if not chunks:
            return MeetingSummary((), (), (), (), (), None)

        chunk_summaries = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_summaries.append(
                await self._request_summary(
                    prompt=self._build_chunk_prompt(chunk, index=index, total=len(chunks))
                )
            )

        if len(chunk_summaries) == 1:
            return chunk_summaries[0]

        return await self._request_summary(
            prompt=self._build_merge_prompt(chunk_summaries)
        )

    async def _request_summary(self, *, prompt: str) -> MeetingSummary:
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
                        "You create a concise business meeting summary in Russian. "
                        "Return only valid JSON matching the schema. "
                        "Use only facts grounded in the provided text. "
                        "If something is unclear, leave the item out or mark the owner as "
                        "`исполнитель не указан`."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "meeting_summary",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "overview": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "decisions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "action_items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "owner": {"type": "string"},
                                        "task": {"type": "string"},
                                        "deadline": {"type": ["string", "null"]},
                                    },
                                    "required": ["owner", "task", "deadline"],
                                },
                            },
                            "open_questions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "risks": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "next_step": {"type": ["string", "null"]},
                        },
                        "required": [
                            "overview",
                            "decisions",
                            "action_items",
                            "open_questions",
                            "risks",
                            "next_step",
                        ],
                    },
                },
            },
        }

        async with httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=timeout) as client:
            response = await client.post("/v1/chat/completions", json=body)
            response.raise_for_status()
            data = response.json()

        parsed = json.loads(data["choices"][0]["message"]["content"])
        return parse_meeting_summary(parsed)

    def _build_chunk_prompt(self, chunk_text: str, *, index: int, total: int) -> str:
        return (
            f"Ниже часть стенограммы встречи ({index}/{total}).\n"
            "Сделай краткое промежуточное саммари в структурированном виде.\n"
            "Нужны разделы: overview, decisions, action_items, open_questions, risks, next_step.\n"
            "Пиши кратко и по делу.\n"
            "overview: 1-3 пункта.\n"
            "decisions: не больше 4 пунктов.\n"
            "action_items: не больше 5 пунктов.\n"
            "open_questions: не больше 4 пунктов.\n"
            "risks: не больше 3 пунктов.\n"
            "next_step: одно короткое предложение или null.\n\n"
            "Текст:\n"
            f"{chunk_text}"
        )

    def _build_merge_prompt(self, chunk_summaries: list[MeetingSummary]) -> str:
        parts = []
        for index, item in enumerate(chunk_summaries, start=1):
            parts.append(f"Чанк {index}:\n{meeting_summary_to_source_text(item)}")

        return (
            "Ниже промежуточные саммари нескольких частей одной встречи.\n"
            "Собери по ним единое итоговое саммари без потери важных кусков.\n"
            "Удали повторы, сохрани решения, поручения, вопросы и риски из всех частей.\n"
            "Нужны разделы: overview, decisions, action_items, open_questions, risks, next_step.\n"
            "Пиши кратко, но не теряй важные факты.\n"
            "overview: 2-3 пункта.\n"
            "decisions: не больше 6 пунктов.\n"
            "action_items: не больше 8 пунктов.\n"
            "open_questions: не больше 6 пунктов.\n"
            "risks: не больше 4 пунктов.\n"
            "next_step: одно короткое предложение или null.\n\n"
            + "\n\n".join(parts)
        )


def parse_meeting_summary(parsed: dict) -> MeetingSummary:
    return MeetingSummary(
        overview=tuple(item.strip() for item in parsed.get("overview", []) if item.strip()),
        decisions=tuple(item.strip() for item in parsed.get("decisions", []) if item.strip()),
        action_items=tuple(
            ActionItem(
                owner=(item.get("owner") or "исполнитель не указан").strip(),
                task=(item.get("task") or "").strip(),
                deadline=(item.get("deadline") or None),
            )
            for item in parsed.get("action_items", [])
            if (item.get("task") or "").strip()
        ),
        open_questions=tuple(item.strip() for item in parsed.get("open_questions", []) if item.strip()),
        risks=tuple(item.strip() for item in parsed.get("risks", []) if item.strip()),
        next_step=(parsed.get("next_step") or None),
    )


def build_summary_text(summary: MeetingSummary, *, meta: MeetingSummaryMeta) -> str:
    sections: list[str] = [f"📝 <b>{escape_summary_value(meta.title, 120)}</b>"]
    sections.append(f"🗓 <b>Дата:</b> {escape_summary_value(meta.meeting_date, 40)}")

    if summary.overview:
        sections.append("")
        sections.append("🧭 <b>Кратко</b>")
        sections.extend(f"• {escape_summary_value(item)}" for item in summary.overview[:3])

    if summary.decisions:
        sections.append("")
        sections.append("✅ <b>Что решили</b>")
        sections.extend(f"• {escape_summary_value(item)}" for item in summary.decisions[:6])

    if summary.action_items:
        sections.append("")
        sections.append("👤 <b>Поручения</b>")
        for item in summary.action_items[:8]:
            line = f"• <b>{escape_summary_value(item.owner, 80)}</b> -> {escape_summary_value(item.task)}"
            if item.deadline:
                line += f"\n  🗓 {escape_summary_value(item.deadline, 60)}"
            sections.append(line)

    if summary.open_questions:
        sections.append("")
        sections.append("❓ <b>Открытые вопросы</b>")
        sections.extend(f"• {escape_summary_value(item)}" for item in summary.open_questions[:6])

    if summary.risks:
        sections.append("")
        sections.append("⚠️ <b>Риски / блокеры</b>")
        sections.extend(f"• {escape_summary_value(item)}" for item in summary.risks[:4])

    if summary.next_step:
        sections.append("")
        sections.append("➡️ <b>Следующий шаг</b>")
        sections.append(escape_summary_value(summary.next_step))

    return "\n".join(sections).strip()


def split_transcript_into_chunks(result: TranscriptResult, *, max_chars: int) -> list[str]:
    if result.utterances:
        lines = [f"{format_speaker_label(item.speaker)}: {item.text.strip()}" for item in result.utterances if item.text.strip()]
        return chunk_lines(lines, max_chars=max_chars)

    text = (result.text or "").strip()
    if not text:
        return []
    return chunk_plain_text(text, max_chars=max_chars)


def chunk_lines(lines: list[str], *, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        clipped = line[:400]
        extra = len(clipped) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append("\n".join(current))
            current = [clipped]
            current_len = len(clipped)
            continue
        current.append(clipped)
        current_len += extra

    if current:
        chunks.append("\n".join(current))
    return chunks


def chunk_plain_text(text: str, *, max_chars: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def meeting_summary_to_source_text(summary: MeetingSummary) -> str:
    sections: list[str] = []

    if summary.overview:
        sections.append("overview:")
        sections.extend(f"- {item}" for item in summary.overview)

    if summary.decisions:
        sections.append("decisions:")
        sections.extend(f"- {item}" for item in summary.decisions)

    if summary.action_items:
        sections.append("action_items:")
        for item in summary.action_items:
            line = f"- {item.owner} -> {item.task}"
            if item.deadline:
                line += f" -> {item.deadline}"
            sections.append(line)

    if summary.open_questions:
        sections.append("open_questions:")
        sections.extend(f"- {item}" for item in summary.open_questions)

    if summary.risks:
        sections.append("risks:")
        sections.extend(f"- {item}" for item in summary.risks)

    if summary.next_step:
        sections.append(f"next_step: {summary.next_step}")

    return "\n".join(sections).strip()


def build_meeting_summary_meta(*, source_name: str | None, meeting_date: str) -> MeetingSummaryMeta:
    return MeetingSummaryMeta(
        title=derive_meeting_title(source_name),
        meeting_date=meeting_date,
    )


def derive_meeting_title(source_name: str | None) -> str:
    stem = Path(source_name or "").stem.strip()
    if not stem or stem.lower() in {"voice", "audio", "video", "document", "video_note"}:
        return "Встреча"
    cleaned = stem.replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned or "Встреча"


def escape_summary_value(value: str, max_len: int = 220) -> str:
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3].rstrip() + "..."
    return html.escape(cleaned)
