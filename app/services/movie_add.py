import logging
from time import perf_counter

from app.core.exceptions import (
    AppException,
    InvalidUpstreamResponseError,
    UpstreamServiceError,
    UpstreamServiceUnavailable,
)
from app.integrations.radarr.client import RadarrClient
from app.integrations.radarr.schemas import RadarrMovieResource
from app.schemas.resources import MovieAddRequest, MovieAddResponseMovie, MovieAddResult

logger = logging.getLogger("app.services.movie_add")


class MovieAddService:
    def __init__(self, radarr_client: RadarrClient | None = None) -> None:
        self.radarr_client = radarr_client or RadarrClient()

    async def add_and_search_movie(self, request: MovieAddRequest) -> MovieAddResult:
        started_at = perf_counter()
        action = "unknown"
        success = False
        error_type = "none"

        try:
            await self._ensure_quality_profile_exists(request.quality_profile_id)
            existing_movie = await self.radarr_client.get_movie_by_tmdb_id(request.tmdb_id)
            if existing_movie is not None:
                action = "updated_existing_then_searched"
                movie = await self._update_existing_movie_and_start_search(
                    movie=existing_movie,
                    request=request,
                )
            else:
                action = "added_then_searched"
                movie, was_added = await self.radarr_client.add_movie_by_tmdb_id(
                    tmdb_id=request.tmdb_id,
                    title=request.title,
                    year=request.year,
                    quality_profile_id=request.quality_profile_id,
                )
                if not was_added:
                    action = "updated_existing_then_searched"
                    movie = await self._update_existing_movie_and_start_search(
                        movie=movie,
                        request=request,
                    )

            if movie.id is None:
                raise InvalidUpstreamResponseError()

            self._ensure_quality_profile_applied(movie=movie, request=request)
            success = True
            return MovieAddResult(
                action=action,
                movie=self._map_movie(movie=movie, request=request),
            )
        except (
            UpstreamServiceUnavailable,
            UpstreamServiceError,
            InvalidUpstreamResponseError,
        ) as exc:
            error_type = exc.__class__.__name__
            logger.warning(
                "Radarr movie add/search failed tmdb_id=%s action=%s error_type=%s",
                request.tmdb_id,
                action,
                error_type,
            )
            raise UpstreamServiceError(message="failed to start movie search") from exc
        except AppException as exc:
            error_type = exc.__class__.__name__
            raise
        except Exception as exc:
            error_type = exc.__class__.__name__
            logger.exception("Unexpected movie add/search error tmdb_id=%s", request.tmdb_id)
            raise
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Movie add/search completed tmdb_id=%s action=%s success=%s duration_ms=%.2f error_type=%s",
                request.tmdb_id,
                action,
                success,
                duration_ms,
                error_type,
            )

    def _map_movie(
        self,
        *,
        movie: RadarrMovieResource,
        request: MovieAddRequest,
    ) -> MovieAddResponseMovie:
        if movie.id is None:
            raise InvalidUpstreamResponseError()

        return MovieAddResponseMovie(
            id=movie.id,
            tmdb_id=movie.tmdb_id or request.tmdb_id,
            title=movie.title or request.title,
            year=movie.year or request.year,
            qualityProfileId=movie.quality_profile_id or request.quality_profile_id,
        )

    async def _ensure_quality_profile_exists(self, quality_profile_id: int) -> None:
        profiles = await self.radarr_client.get_quality_profiles()
        valid_profile_ids = {profile.id for profile in profiles if profile.id is not None}
        if quality_profile_id not in valid_profile_ids:
            raise AppException(status_code=400, message="invalid qualityProfileId")

    async def _update_existing_movie_and_start_search(
        self,
        *,
        movie: RadarrMovieResource,
        request: MovieAddRequest,
    ) -> RadarrMovieResource:
        updated_movie = await self.radarr_client.update_movie_quality_profile(
            movie=movie,
            quality_profile_id=request.quality_profile_id,
        )
        self._ensure_quality_profile_applied(movie=updated_movie, request=request)
        if updated_movie.id is None:
            raise InvalidUpstreamResponseError()

        await self.radarr_client.start_movie_search(updated_movie.id)
        return updated_movie

    def _ensure_quality_profile_applied(
        self,
        *,
        movie: RadarrMovieResource,
        request: MovieAddRequest,
    ) -> None:
        if (
            movie.quality_profile_id is not None
            and movie.quality_profile_id != request.quality_profile_id
        ):
            raise UpstreamServiceError(message="failed to start movie search")
