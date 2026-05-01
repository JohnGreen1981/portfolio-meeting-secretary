# Cleanup Plan

- [x] Copy `meeting_secretary/`, `main.py`, `Dockerfile`, `docker-compose.yml`, docs and requirements if safe.
- [x] Exclude `.env`, `.env.vps`, `.agents/logs/`, `.venv`, caches and real transcripts.
- [x] Create neutral `.env.example` and `.env.vps.example`.
- [x] Replace deployment paths/domains with placeholders.
- [ ] Add demo transcript generated from synthetic or public-domain audio.
- [x] Run syntax check with `python3 -m py_compile`.
- [x] Run secret scan before first GitHub push.
