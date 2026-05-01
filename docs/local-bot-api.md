# Local Bot API для больших файлов

Цель: дать боту доступ к файлам конференций больше `20 MB`.

## Что нужно

- VPS, где будет жить и бот, и `telegram-bot-api`
- `api_id` и `api_hash` Telegram с `my.telegram.org`
- общий каталог или volume, который виден и `telegram-bot-api`, и самому боту по одному и тому же пути

## Почему нужен общий storage

В local mode `getFile` возвращает абсолютный путь к файлу. `aiogram` в этом режиме читает файл локально,
а не скачивает его через обычный `https://api.telegram.org/file/...`.

Значит, если `telegram-bot-api` пишет файлы в `/var/lib/telegram-bot-api`, бот тоже должен видеть этот путь.

## Минимальная docker-compose схема

Ниже практичный shortcut через Docker image `aiogram/telegram-bot-api`. Это не официальный образ Telegram,
а обертка над официальным сервером `tdlib/telegram-bot-api`. Если нужен строго официальный путь, сервер
нужно собрать по инструкции из репозитория `tdlib/telegram-bot-api`.

```yaml
services:
  telegram-bot-api:
    image: aiogram/telegram-bot-api:latest
    restart: unless-stopped
    command:
      - --api-id=${TELEGRAM_API_ID}
      - --api-hash=${TELEGRAM_API_HASH}
      - --local
      - --dir=/var/lib/telegram-bot-api
      - --http-port=8081
    volumes:
      - telegram-bot-api-data:/var/lib/telegram-bot-api
    ports:
      - "127.0.0.1:8081:8081"

  meeting-secretary:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    environment:
      TELEGRAM_BOT_API_BASE_URL: http://telegram-bot-api:8081
      TELEGRAM_BOT_API_LOCAL_MODE: "true"
    volumes:
      - telegram-bot-api-data:/var/lib/telegram-bot-api
    depends_on:
      - telegram-bot-api

volumes:
  telegram-bot-api-data:
```

## Перед переключением бота на local server

Нужно разлогинить бота из cloud Bot API:

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/logOut"
```

После этого запускать бота уже через local server.

## Что проверить после деплоя

1. контейнер `telegram-bot-api` поднялся
2. `/ping` у бота отвечает
3. файл больше `20 MB` принимается без ошибки про cloud Bot API
4. в логах бота видно `telegram_api_mode=local`

## Что это еще не решает

- бот пока держит входной файл в памяти перед отправкой в AssemblyAI
- дробление очень больших файлов не реализовано
- retry/resume на уровне кусков пока нет

То есть `Local Bot API` снимает транспортный лимит Telegram, но не отменяет дальнейшую оптимизацию обработки.
