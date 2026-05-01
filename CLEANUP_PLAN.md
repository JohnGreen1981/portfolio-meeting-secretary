# Cleanup Plan

- [ ] Copy `meeting_secretary/`, `main.py`, `Dockerfile`, `docker-compose.yml`, docs and requirements if safe.
- [ ] Exclude `.env`, `.env.vps`, `.agents/logs/`, `.venv`, caches and real transcripts.
- [ ] Create neutral `.env.example` and `.env.vps.example`.
- [ ] Replace deployment paths/domains with placeholders.
- [ ] Add demo transcript generated from synthetic or public-domain audio.
- [ ] Run secret scan before first GitHub push.

