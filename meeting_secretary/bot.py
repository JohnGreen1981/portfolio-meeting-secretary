"""Telegram bot for meeting transcription."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from meeting_secretary.config import Settings, load_settings
from meeting_secretary.media_metadata import extract_media_recorded_at
from meeting_secretary.meeting_summary import (
    OpenAIMeetingSummaryBuilder,
    build_meeting_summary_meta,
    build_summary_text,
)
from meeting_secretary.speaker_mapping import OpenAISpeakerMapper, SpeakerMappingHint
from meeting_secretary.transcription import (
    AssemblyAIClient,
    SpeakerIdentificationRequest,
    build_transcript_filename,
    build_transcript_text,
    summarize_transcript,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".amr",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".webm",
}


def build_router(settings: Settings) -> Router:
    router = Router(name="meeting_secretary")
    assemblyai = AssemblyAIClient(
        api_key=settings.assemblyai_api_key,
        base_url=settings.assemblyai_base_url,
        speech_models=settings.assemblyai_speech_models,
        language_code=settings.assemblyai_language_code,
        min_speakers=settings.assemblyai_min_speakers,
        max_speakers=settings.assemblyai_max_speakers,
        poll_interval_seconds=settings.assemblyai_poll_interval_seconds,
        timeout_seconds=settings.assemblyai_timeout_seconds,
    )
    openai_speaker_mapper = build_openai_speaker_mapper(settings)
    openai_meeting_summary_builder = build_openai_meeting_summary_builder(settings)

    @router.message(Command("start", "help"))
    async def handle_start(message: Message) -> None:
        if not is_allowed(message, settings):
            return

        await message.answer(
            "🎙️ Отправь запись встречи, и я верну полную стенограмму файлом .txt.\n\n"
            "📎 Поддерживаются voice, audio, video, video_note и файлы с аудио/видео.\n"
            "🤖 После расшифровки я сам попробую определить имена и роли спикеров по контексту разговора.\n"
            "Если уверенности не хватит, оставлю нейтральную метку или помечу роль как предположение."
        )

    @router.message(Command("ping"))
    async def handle_ping(message: Message) -> None:
        if not is_allowed(message, settings):
            return

        models = ", ".join(settings.assemblyai_speech_models)
        language = settings.assemblyai_language_code or "auto"
        await message.answer(
            f"meeting-secretary {settings.app_build}\n"
            f"telegram_api_mode: {settings.telegram_api_mode_label}\n"
            f"speech_models: {models}\n"
            f"language_code: {language}"
        )

    @router.message(F.voice | F.audio | F.video | F.video_note | F.document)
    async def handle_media(message: Message, bot: Bot) -> None:
        if not is_allowed(message, settings):
            return

        source = extract_media_source(message)
        if source is None:
            await message.answer(
                "🤔 Я такое не обработаю.\n\n"
                "Пришли голосовое сообщение, аудио, видео или файл с поддерживаемым расширением."
            )
            return

        cloud_download_limit = settings.telegram_cloud_download_limit_bytes
        if (
            cloud_download_limit is not None
            and source.file_size is not None
            and source.file_size > cloud_download_limit
        ):
            await message.answer(
                "📦 Файл больше 20 MB.\n\n"
                "В обычном Telegram Bot API такие файлы не скачиваются. "
                "Чтобы принимать большие конференции, бота нужно запускать через Local Bot API server."
            )
            return

        if source.file_size is not None and source.file_size > settings.max_input_bytes:
            await message.answer(
                f"🚫 Файл слишком большой: {source.file_size // (1024 * 1024)} MB.\n\n"
                f"Текущий лимит бота: {settings.max_input_mb} MB."
            )
            return

        processing_message = await message.answer(
            "📥 Файл получен\n"
            "Запись принял. Сейчас начну обработку."
        )
        status = ProcessingStatus(processing_message)
        await status.start()

        try:
            await status.update(
                "☁️ Загружаю запись",
                "Отправляю файл в движок расшифровки.",
            )
            file = await bot.get_file(source.file_id)
            suffix = Path(source.file_name or "").suffix or ".bin"
            with NamedTemporaryFile(suffix=suffix) as temp_file:
                await bot.download(file, destination=temp_file)
                temp_path = Path(temp_file.name)
                temp_file.flush()
                recorded_at = extract_media_recorded_at(temp_path)
                audio_bytes = temp_path.read_bytes()

                await status.update(
                    "🧠 Расшифровываю",
                    "Стенограмма строится. Для длинной встречи это может занять несколько минут.",
                )
                speaker_identification = resolve_speaker_identification(message.caption, settings)
                speaker_mapping_hint = resolve_speaker_mapping_hint(message.caption, settings)
                upload_url = await assemblyai.upload_audio(audio_bytes)
                transcript_id = await assemblyai.submit_transcript(
                    upload_url,
                    speaker_identification=speaker_identification,
                )
                result = await assemblyai.wait_for_transcript(transcript_id)
                if openai_speaker_mapper is not None and speaker_mapping_hint is not None:
                    try:
                        result = await openai_speaker_mapper.remap(result, hint=speaker_mapping_hint)
                    except Exception:
                        logger.exception("OpenAI speaker remapping failed")

                summary_text: str | None = None
                if openai_meeting_summary_builder is not None:
                    await status.update(
                        "📝 Готовлю саммари",
                        "Собираю краткую выжимку встречи и список действий.",
                    )
                    try:
                        summary = await openai_meeting_summary_builder.summarize(result)
                        meeting_date = (
                            recorded_at.astimezone().strftime("%d.%m.%Y")
                            if recorded_at is not None and recorded_at.tzinfo is not None
                            else (
                                recorded_at.strftime("%d.%m.%Y")
                                if recorded_at is not None
                                else message.date.astimezone().strftime("%d.%m.%Y")
                            )
                        )
                        summary_text = build_summary_text(
                            summary,
                            meta=build_meeting_summary_meta(
                                source_name=source.file_name,
                                meeting_date=meeting_date,
                            ),
                        )
                    except Exception:
                        logger.exception("OpenAI meeting summary failed")

                transcript_text = build_transcript_text(result, source_name=source.file_name)
                transcript_file = BufferedInputFile(
                    transcript_text.encode("utf-8"),
                    filename=build_transcript_filename(source.file_name),
                )

                if summary_text:
                    await message.answer(summary_text, parse_mode=ParseMode.HTML)

                await message.answer_document(
                    transcript_file,
                    caption=summarize_transcript(result),
                )

                if len(result.text) <= 3500 and not result.utterances:
                    await message.answer(result.text or "[пустой результат]")

                await status.finish(
                    "📄 Готово",
                    "Стенограмма и саммари отправлены." if summary_text else "Стенограмма отправлена.",
                )
        except Exception as exc:
            logger.exception("Failed to process media")
            await status.fail(f"Не удалось расшифровать запись: {exc}")

    @router.message()
    async def handle_other(message: Message) -> None:
        if not is_allowed(message, settings):
            return

        await message.answer(
            "📭 Жду запись встречи: voice, audio, video, video_note или файл с аудио/видео."
        )

    return router


async def run_bot() -> None:
    settings = load_settings()
    logger.info(
        "Starting meeting secretary bot build=%s telegram_api_mode=%s",
        settings.app_build,
        settings.telegram_api_mode_label,
    )
    bot = create_bot(settings)
    dp = Dispatcher()
    dp.include_router(build_router(settings))
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def create_bot(settings: Settings) -> Bot:
    if not settings.telegram_bot_api_base_url:
        return Bot(token=settings.telegram_bot_token)

    api = TelegramAPIServer.from_base(
        settings.telegram_bot_api_base_url,
        is_local=settings.telegram_bot_api_local_mode,
    )
    session = AiohttpSession(api=api)
    return Bot(token=settings.telegram_bot_token, session=session)


def build_openai_speaker_mapper(settings: Settings) -> OpenAISpeakerMapper | None:
    if not settings.openai_api_key:
        return None
    return OpenAISpeakerMapper(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_speaker_mapping_model,
        confidence_threshold=settings.openai_speaker_mapping_confidence_threshold,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def build_openai_meeting_summary_builder(settings: Settings) -> OpenAIMeetingSummaryBuilder | None:
    if not settings.openai_api_key:
        return None
    return OpenAIMeetingSummaryBuilder(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_meeting_summary_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def is_allowed(message: Message, settings: Settings) -> bool:
    user = message.from_user
    if user is None:
        return False
    return settings.owner_id == 0 or user.id == settings.owner_id


class MediaSource:
    def __init__(self, *, file_id: str, file_name: str | None, file_size: int | None) -> None:
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size


def extract_media_source(message: Message) -> MediaSource | None:
    if message.voice:
        return MediaSource(
            file_id=message.voice.file_id,
            file_name="voice.ogg",
            file_size=message.voice.file_size,
        )

    if message.audio:
        return MediaSource(
            file_id=message.audio.file_id,
            file_name=message.audio.file_name or "audio.mp3",
            file_size=message.audio.file_size,
        )

    if message.video:
        return MediaSource(
            file_id=message.video.file_id,
            file_name=message.video.file_name or "video.mp4",
            file_size=message.video.file_size,
        )

    if message.video_note:
        return MediaSource(
            file_id=message.video_note.file_id,
            file_name="video_note.mp4",
            file_size=message.video_note.file_size,
        )

    if message.document:
        mime_type = (message.document.mime_type or "").lower()
        suffix = Path(message.document.file_name or "").suffix.lower()
        if mime_type.startswith(("audio/", "video/")) or suffix in SUPPORTED_DOCUMENT_EXTENSIONS:
            return MediaSource(
                file_id=message.document.file_id,
                file_name=message.document.file_name or "document",
                file_size=message.document.file_size,
            )

    return None


def resolve_speaker_identification(
    caption: str | None,
    settings: Settings,
) -> SpeakerIdentificationRequest | None:
    from_caption = parse_speaker_identification_caption(caption)
    if from_caption is not None:
        return from_caption

    if (
        settings.assemblyai_speaker_identification_type
        and settings.assemblyai_speaker_identification_values
    ):
        return SpeakerIdentificationRequest(
            speaker_type=settings.assemblyai_speaker_identification_type,
            known_values=settings.assemblyai_speaker_identification_values,
        )

    return None


def resolve_speaker_mapping_hint(
    caption: str | None,
    settings: Settings,
) -> SpeakerMappingHint | None:
    identification = resolve_speaker_identification(caption, settings)
    if identification is not None and len(identification.known_values) >= 2:
        return SpeakerMappingHint(
            speaker_type=identification.speaker_type,
            candidates=identification.known_values,
        )

    if settings.openai_api_key:
        return SpeakerMappingHint(speaker_type="inferred_role")

    return None


def parse_speaker_identification_caption(caption: str | None) -> SpeakerIdentificationRequest | None:
    if not caption:
        return None

    for raw_line in caption.splitlines():
        line = raw_line.strip()
        lower = line.lower()

        if lower.startswith("спикеры:") or lower.startswith("speakers:"):
            values = tuple(part.strip() for part in line.split(":", 1)[1].split(",") if part.strip())
            if values:
                return SpeakerIdentificationRequest(speaker_type="name", known_values=values)

        if lower.startswith("роли:") or lower.startswith("roles:"):
            values = tuple(part.strip() for part in line.split(":", 1)[1].split(",") if part.strip())
            if values:
                return SpeakerIdentificationRequest(speaker_type="role", known_values=values)

    return None


def limit_message_text(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


class ProcessingStatus:
    def __init__(self, message: Message) -> None:
        self._message = message
        self._title = "📥 Файл получен"
        self._detail = "Запись принял. Сейчас начну обработку."
        self._phase_started_at = asyncio.get_running_loop().time()
        self._last_notified_minute = 0
        self._ticker_task: asyncio.Task | None = None
        self._closed = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._ticker_task = asyncio.create_task(self._ticker())

    async def update(self, title: str, detail: str) -> None:
        async with self._lock:
            self._title = title
            self._detail = detail
            self._phase_started_at = asyncio.get_running_loop().time()
            self._last_notified_minute = 0
            await self._render()

    async def finish(self, title: str, detail: str) -> None:
        await self._stop_ticker()
        async with self._lock:
            self._title = title
            self._detail = detail
            await self._render()

    async def fail(self, text: str) -> None:
        await self._stop_ticker()
        try:
            await self._message.edit_text(text)
        except Exception:
            logger.exception("Failed to render failure status")

    async def _ticker(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(15)
                elapsed = int(asyncio.get_running_loop().time() - self._phase_started_at)
                elapsed_minutes = elapsed // 60
                if elapsed_minutes < 1 or elapsed_minutes <= self._last_notified_minute:
                    continue

                async with self._lock:
                    elapsed = int(asyncio.get_running_loop().time() - self._phase_started_at)
                    elapsed_minutes = elapsed // 60
                    if elapsed_minutes < 1 or elapsed_minutes <= self._last_notified_minute:
                        continue
                    self._last_notified_minute = elapsed_minutes
                    await self._render(extra=f"⏱ Все еще работаю: {format_elapsed(elapsed)}.")
        except asyncio.CancelledError:
            return

    async def _stop_ticker(self) -> None:
        self._closed = True
        if self._ticker_task is not None:
            self._ticker_task.cancel()
            try:
                await self._ticker_task
            except asyncio.CancelledError:
                pass

    async def _render(self, extra: str | None = None) -> None:
        text = f"{self._title}\n{self._detail}"
        if extra:
            text += f"\n\n{extra}"
        try:
            await self._message.edit_text(text)
        except Exception:
            logger.exception("Failed to render processing status")


def format_elapsed(total_seconds: int) -> str:
    minutes, seconds = divmod(max(total_seconds, 0), 60)
    if minutes == 0:
        return f"{seconds} сек."
    if seconds == 0:
        return f"{minutes} мин."
    return f"{minutes} мин. {seconds} сек."
