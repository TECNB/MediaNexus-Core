# MediaNexus Backend

MediaNexus Backend is a lightweight FastAPI skeleton for a media resource management platform.

This repository currently focuses on a clean backend foundation plus minimal search proxy integrations for Radarr and Sonarr:

- FastAPI application entrypoint
- Pydantic Settings based configuration
- Unified API response shape
- Basic exception handling
- Simple logging setup
- SQLAlchemy session infrastructure
- Alembic initialization
- Radarr movie search integration
- Sonarr series search integration
- Reserved directories for future integrations such as Sonarr, Emby, Bazarr, OpenList, CloudDrive2, and AutoSymlink

Only search proxy endpoints are implemented for external integrations in this stage.

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

## Sonarr Series Search

Configure Sonarr in `.env`:

```bash
SONARR_SCHEME=http
SONARR_HOST=127.0.0.1
SONARR_PORT=8989
SONARR_API_KEY=your_sonarr_api_key
SONARR_TIMEOUT=10
```

`SONARR_HOST` should be only the host or IP, without scheme or path.

After the backend is running, test the proxy endpoint:

```bash
curl "http://127.0.0.1:8000/api/v1/resources/series/search?term=breaking%20bad"
```

The API returns a frontend-friendly mapped series list in the unified response format:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "tvdb:81189",
        "title": "Breaking Bad",
        "original_title": null,
        "year": 2008,
        "overview": "...",
        "poster": "https://...",
        "tvdb_id": 81189,
        "imdb_id": "tt0903747",
        "tmdb_id": 1396,
        "status": "ended",
        "network": "AMC",
        "series_type": "standard"
      }
    ]
  }
}
```

Failure responses stay in the same envelope. Typical cases are:

- `400` when `term` is missing or blank
- `503` when Sonarr is unreachable or not configured
- `502` when Sonarr returns a non-2xx response or invalid payload

## Subtitle Upload And Emby Refresh

Subtitle upload can optionally notify Emby after files are copied to the STRM library.

Configure Emby in `.env`:

```bash
EMBY_URL=http://127.0.0.1:8096
EMBY_API_KEY=your_emby_api_key
EMBY_TIMEOUT=10
EMBY_PATH_PREFIX_FROM=/strm
EMBY_PATH_PREFIX_TO=/srv/media/STRM
```

Refresh behavior:

- After subtitle files are uploaded, the backend derives the corresponding media file path for each uploaded subtitle.
- It first queries Emby with the exact media path and refreshes only the matched `Movie` or `Episode` item.
- If an exact item match is not found, it falls back to notifying Emby through `Library/Media/Updated` for the unresolved path.
- If Emby is not configured or temporarily unavailable, subtitle upload still succeeds and the refresh step is skipped with a warning in server logs.

Upload modes for `POST /api/v1/subtitles/upload`:

- Manual mode: send `target_path` directly. The path must stay under `/srv/media/STRM/Movie`, `/srv/media/STRM/TV`, or `/srv/media/STRM/Anime`.
- Movie association mode: send `media_type=movie` together with `tmdb_id` and optionally `imdb_id`.
- In movie association mode the backend first asks Radarr for an existing movie and prefers Radarr's `path` when present.
- If Radarr does not return a usable `path`, the backend falls back to Radarr's English `title + year` and builds `/srv/media/STRM/Movie/{title} ({year})`.
- Legacy `library_title` and `library_year` fields are still accepted for backward compatibility, but the new directory resolution flow no longer depends on them.

Typical failure responses:

- `400` for invalid upload mode, missing stable media ID, or an unsafe target directory
- `404` when Radarr cannot find the requested movie
- `503` when Radarr is unreachable or not configured
- `502` when Radarr returns an invalid response

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
- Sonarr series search proxy endpoint
- Environment based settings
- CORS configuration
- Unified response schema
- Base exception handling
- SQLAlchemy engine and session factory
- Alembic environment setup
- Integration placeholders

Not implemented on purpose:

- Radarr add movie or any write operation
- Sonarr add series or any write operation
- Business services
- Authentication and authorization
- User system
- Task queue
- Redis or Celery
- WebSocket support
- Deployment stack such as Docker Compose
- Real business models and migrations
