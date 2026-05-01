# Meeting Secretary

## Назначение

Очищенный портфельный репозиторий Telegram-бота, который расшифровывает записи встреч и возвращает структурированное summary.

Репозиторий предназначен для публичной проверки. В нём не должно быть приватных записей, стенограмм, логов, токенов, VPS-доступов и имён реальных участников встреч.

## Стек

- Python 3.11
- aiogram 3
- httpx
- AssemblyAI Speech-to-Text
- OpenAI API для опционального speaker mapping и summary
- Docker / Docker Compose
- Telegram Local Bot API для больших файлов

## Структура

```text
main.py                         точка входа
meeting_secretary/bot.py        Telegram handlers и основной сценарий обработки
meeting_secretary/config.py     загрузка настроек
meeting_secretary/transcription.py
meeting_secretary/speaker_mapping.py
meeting_secretary/meeting_summary.py
meeting_secretary/media_metadata.py
docs/local-bot-api.md
```

## AI-assisted development

Проект представлен как прототип автоматизации, собранный с помощью AI-assisted development. В портфолио акцент на проектировании пользовательского сценария, промптов и контрольных решений, интеграции API, ограничениях размера файлов, ручной проверке сценариев и документации.

Не описывать проект как production backend, написанный вручную с нуля.

## Правила

- Не коммитить `.env`, `.env.vps`, токены, записи, стенограммы, логи и приватные данные встреч.
- `.env.example` и `.env.vps.example` должны содержать только placeholder-значения.
- При изменении runtime-кода запускать `python3 -m py_compile main.py meeting_secretary/*.py`.
- Использовать только синтетические или public-domain demo data.
- Важные summary сверять со стенограммой.
