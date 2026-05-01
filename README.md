# Meeting Secretary

Telegram-бот для расшифровки встреч и подготовки структурированного summary.

Это очищенная портфельная версия. В репозитории нет production `.env`, записей встреч, приватных стенограмм, логов, имён реальных участников и VPS-доступов.

## Что показывает проект

- Сценарий speech-to-text для длинных аудио/видео.
- Диаризацию спикеров и сопоставление спикеров с именами/ролями.
- Пошаговую сборку summary для длинных стенограмм.
- Архитектуру Telegram Local Bot API для файлов больше лимита cloud Bot API.
- Сценарий деплоя через Docker / Docker Compose.
- AI-assisted development: постановка задачи, реализация через coding assistants, ручная проверка сценариев, очистка и документация.

## Пользовательский сценарий

1. Пользователь отправляет запись встречи в Telegram-бота.
2. Бот проверяет тип и размер файла.
3. Бот отправляет аудио/видео в AssemblyAI и ждёт diarized transcription.
4. Бот опционально использует GPT, чтобы вывести имена или роли спикеров из контекста.
5. Бот опционально собирает структурированное summary встречи.
6. Пользователь получает `.txt`-файл со стенограммой и короткое summary сообщением.

## Стек

- Python 3.11
- aiogram 3
- httpx
- AssemblyAI Speech-to-Text API
- OpenAI API для speaker mapping и summary
- Docker / Docker Compose
- Telegram Local Bot API для больших файлов

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Нужные переменные окружения:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
OPENAI_API_KEY=your_openai_api_key_optional
OWNER_ID=your_telegram_user_id
```

`OPENAI_API_KEY` опционален. Без него бот может возвращать стенограммы, но GPT speaker mapping и meeting summary будут отключены.

## Docker

Режим Cloud Bot API:

```bash
docker build -t meeting-secretary .
docker run -d \
  --name meeting-secretary \
  --restart unless-stopped \
  --env-file .env \
  meeting-secretary
```

Режим Local Bot API для файлов больше лимита скачивания Cloud Bot API:

```bash
cp .env.vps.example .env.vps
docker compose up -d --build
```

Подробности: [docs/local-bot-api.md](docs/local-bot-api.md).

## Структура

```text
main.py                         точка входа
meeting_secretary/bot.py        Telegram handlers и processing workflow
meeting_secretary/config.py     настройки окружения
meeting_secretary/transcription.py
meeting_secretary/speaker_mapping.py
meeting_secretary/meeting_summary.py
meeting_secretary/media_metadata.py
docs/local-bot-api.md           заметки по Local Bot API
```

## Безопасность

- Не коммитить `.env`, `.env.vps`, реальные записи, приватные стенограммы и логи.
- Использовать только синтетические или public-domain demo recordings.
- Speaker mapping может быть неточным; низкая уверенность должна оставлять нейтральные метки.
- Summary — вспомогательный output, важные решения нужно сверять со стенограммой.

## Портфельная рамка

Проект представлен как прототип автоматизации, собранный с помощью AI-assisted development. Фокус: проектирование пользовательского сценария, промптов и контрольных решений, ограничения больших файлов, интеграция API и практичный UX, а не заявление о ручной production backend-разработке.
