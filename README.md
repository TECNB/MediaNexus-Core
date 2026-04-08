# MediaNexus Backend

MediaNexus Backend is a lightweight FastAPI skeleton for a media resource management platform.

This repository currently focuses on a clean backend foundation plus a minimal Radarr movie search proxy:

- FastAPI application entrypoint
- Pydantic Settings based configuration
- Unified API response shape
- Basic exception handling
- Simple logging setup
- SQLAlchemy session infrastructure
- Alembic initialization
- Radarr movie search integration
- Reserved directories for future integrations such as Sonarr, Emby, Bazarr, OpenList, CloudDrive2, and AutoSymlink

Only movie search is implemented for external integration in this stage.

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Pydantic Settings
- SQLAlchemy
- Alembic
- httpx

## Project Structure

```text
MediaNexus-Core/
  app/
    api/
    core/
    db/
    integrations/
    models/
    schemas/
    services/
    main.py
  alembic/
  alembic.ini
  requirements.txt
  .env.example
  .gitignore
  README.md
```

## Getting Started

### 1. Create a virtual environment

```bash
python3 -m venv .venv
```

### 2. Install dependencies

```bash
.venv/bin/pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Update values in `.env` as needed. Sensitive values must stay in environment variables and should not be committed.

### 4. Start the development server

```bash
.venv/bin/uvicorn app.main:app --reload
```

The API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Health Check Endpoints

- [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- [http://127.0.0.1:8000/api/v1/health/ping](http://127.0.0.1:8000/api/v1/health/ping)

## Radarr Movie Search

Configure Radarr in `.env`:

```bash
RADARR_SCHEME=http
RADARR_HOST=127.0.0.1
RADARR_PORT=7878
RADARR_API_KEY=your_radarr_api_key
RADARR_TIMEOUT=10
```

`RADARR_HOST` should be only the host or IP, without scheme or path. For example, use `127.0.0.1`, not `http://127.0.0.1:7878`.

After the backend is running, test the proxy endpoint:

```bash
curl "http://127.0.0.1:8000/api/v1/resources/movies/search?term=interstellar"
```

The API returns a frontend-friendly mapped movie list in the unified response format:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "tmdb:157336",
        "title": "Interstellar",
        "original_title": "Interstellar",
        "year": 2014,
        "overview": "...",
        "poster": "https://...",
        "tmdb_id": 157336,
        "imdb_id": "tt0816692",
        "status": "released"
      }
    ]
  }
}
```

Failure responses stay in the same envelope. Typical cases are:

- `400` when `term` is blank
- `503` when Radarr is unreachable or not configured
- `502` when Radarr returns a non-2xx response or invalid payload

## Alembic Status

Alembic has been initialized and wired to the application settings.

At this stage:

- No business models are defined yet
- No migration revision file is created yet
- `alembic upgrade head` is safe to run, but there is nothing to migrate

Common Alembic commands:

```bash
.venv/bin/alembic upgrade head
.venv/bin/alembic revision -m "init"
```

## Current Scope

Implemented:

- Application skeleton
- Versioned API router
- Health check endpoints
- Radarr movie search proxy endpoint
- Environment based settings
- CORS configuration
- Unified response schema
- Base exception handling
- SQLAlchemy engine and session factory
- Alembic environment setup
- Integration placeholders

Not implemented on purpose:

- Radarr add movie or any write operation
- Sonarr or any other external system integration
- Business services
- Authentication and authorization
- User system
- Task queue
- Redis or Celery
- WebSocket support
- Deployment stack such as Docker Compose
- Real business models and migrations
