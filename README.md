# MediaServer

Run the app locally in Docker.

## Prerequisites
- Docker + Docker Compose
- A TMDB API key

## Quick start
1. Copy environment template and fill values:
   ```bash
   cp .env.example .env
   ```
2. Set `TMDB_API_KEY` in `.env`.
3. (Optional) put media files in `./media`.
4. Build and run:
   ```bash
   docker compose up --build
   ```
5. Open `http://localhost:5000`.

## Notes
- SQLite DB is persisted in `./data`.
- HLS output is persisted in `./playback_output`.
- Media library mount is `./media`.
