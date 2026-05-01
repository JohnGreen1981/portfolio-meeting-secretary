# Meeting Secretary

## Назначение

Репозиторий Telegram-бота, который расшифровывает записи встреч и возвращает структурированное summary.

В репозитории не хранить приватные записи, стенограммы, логи, токены, VPS-доступы и имена реальных участников встреч.

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

Проект показывает прототип автоматизации, собранный с помощью AI-assisted development: проектирование пользовательского сценария, промптов и контрольных решений, интеграцию API, учёт ограничений размера файлов, ручную проверку сценариев и документацию.

Не описывать проект как production backend, написанный вручную с нуля.

## Правила

- Не коммитить `.env`, `.env.vps`, токены, записи, стенограммы, логи и приватные данные встреч.
- `.env.example` и `.env.vps.example` должны содержать только placeholder-значения.
- При изменении runtime-кода запускать `python3 -m py_compile main.py meeting_secretary/*.py`.
- Использовать только синтетические или открытые demo data.
- Важные summary сверять со стенограммой.
