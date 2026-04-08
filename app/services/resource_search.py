import logging
import re
from time import perf_counter

from app.core.exceptions import AppException
from app.integrations.radarr.client import RadarrClient
from app.integrations.radarr.schemas import RadarrMovieImage, RadarrMovieLookupItem
from app.schemas.resources import MovieSearchItem, MovieSearchResult

logger = logging.getLogger("app.services.resource_search")


class MovieSearchService:
    def __init__(self, radarr_client: RadarrClient | None = None) -> None:
        self.radarr_client = radarr_client or RadarrClient()

    async def search_movies(self, term: str) -> MovieSearchResult:
        started_at = perf_counter()
        success = False
        result_count = 0
        error_type = "none"

        try:
            movies = await self.radarr_client.search_movies(term=term)
            items = [self._map_movie(movie) for movie in movies]
            result_count = len(items)
            success = True
            return MovieSearchResult(items=items)
        except AppException as exc:
            error_type = exc.__class__.__name__
            raise
        except Exception as exc:
            error_type = exc.__class__.__name__
            logger.exception("Unexpected movie search error for term=%r", term)
            raise
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Movie search completed term=%r success=%s results=%s duration_ms=%.2f error_type=%s",
                term,
                success,
                result_count,
                duration_ms,
                error_type,
            )

    def _map_movie(self, movie: RadarrMovieLookupItem) -> MovieSearchItem:
        title = (movie.title or "").strip() or "Unknown Title"
        return MovieSearchItem(
            id=self._build_movie_id(movie, title=title),
            title=title,
            original_title=(movie.original_title or "").strip() or None,
            year=movie.year,
            overview=(movie.overview or "").strip(),
            poster=self._extract_poster(movie.images),
            tmdb_id=movie.tmdb_id,
            imdb_id=movie.imdb_id,
            status=self._map_status(movie),
        )

    def _build_movie_id(self, movie: RadarrMovieLookupItem, *, title: str) -> str:
        if movie.tmdb_id is not None:
            return f"tmdb:{movie.tmdb_id}"
        if movie.imdb_id:
            return f"imdb:{movie.imdb_id}"
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or "unknown"
        safe_year = str(movie.year) if movie.year is not None else "unknown"
        return f"{safe_title}-{safe_year}"

    def _extract_poster(self, images: list[RadarrMovieImage]) -> str | None:
        for image in images:
            if (image.cover_type or "").lower() == "poster":
                return image.remote_url or image.url
        return None

    def _map_status(self, movie: RadarrMovieLookupItem) -> str:
        for candidate in (movie.status, movie.minimum_availability):
            normalized = self._normalize_status(candidate)
            if normalized is not None:
                return normalized

        if movie.is_available or any(
            self._has_text_value(value)
            for value in (movie.in_cinemas, movie.digital_release, movie.physical_release)
        ):
            return "released"

        return "unknown"

    def _normalize_status(self, value: str | None) -> str | None:
        if not value:
            return None

        normalized = value.strip().lower()
        if normalized in {"released", "available", "incinemas", "in_cinemas", "in cinemas"}:
            return "released"
        if normalized in {"announced", "predb", "tba"}:
            return "announced"
        return None

    def _has_text_value(self, value: str | None) -> bool:
        return bool(value and value.strip())
