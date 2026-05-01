# План очистки

- [x] Перенести `meeting_secretary/`, `main.py`, `Dockerfile`, `docker-compose.yml`, docs и requirements.
- [x] Исключить `.env`, `.env.vps`, `.agents/logs/`, `.venv`, кэши и реальные стенограммы.
- [x] Создать нейтральные `.env.example` и `.env.vps.example`.
- [x] Заменить пути и домены деплоя на placeholder-значения.
- [ ] Добавить демо-стенограмму на синтетической записи или аудио из public domain.
- [x] Проверить синтаксис через `python3 -m py_compile`.
- [x] Запустить проверку на секреты перед первой публикацией в GitHub.
