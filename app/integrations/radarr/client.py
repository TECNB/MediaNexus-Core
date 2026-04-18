import logging
import re
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    InvalidUpstreamResponseError,
    UpstreamServiceError,
    UpstreamServiceUnavailable,
)
from app.integrations.radarr.schemas import (
    RadarrMovieLookupItem,
    RadarrMovieLookupResponse,
    RadarrMovieResource,
    RadarrMovieResourceResponse,
    RadarrQualityProfile,
    RadarrQualityProfileResponse,
    RadarrRootFolderResponse,
)

logger = logging.getLogger("app.integrations.radarr")


class RadarrClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def base_url(self) -> str:
        host = (self.settings.radarr_host or "").strip().rstrip("/")
        if not host:
            raise UpstreamServiceUnavailable(message="Radarr 服务尚未配置")

        base_url = f"{self.settings.radarr_scheme}://{host}"
        if self.settings.radarr_port is not None:
            base_url = f"{base_url}:{self.settings.radarr_port}"
        return base_url

    def _build_headers(self) -> dict[str, str]:
        if not self.settings.radarr_api_key:
            raise UpstreamServiceUnavailable(message="Radarr 服务尚未配置")
        return {"X-Api-Key": self.settings.radarr_api_key}

    async def search_movies(self, term: str) -> list[RadarrMovieLookupItem]:
        response = await self._request(
            "GET",
            "/api/v3/movie/lookup",
            params={"term": term},
            operation="movie lookup",
        )
        payload = self._json(response=response, operation="movie lookup")

        try:
            return RadarrMovieLookupResponse.model_validate(payload).root
        except ValidationError as exc:
            logger.error(
                "Radarr response validation failed for term=%r error_count=%s",
                term,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc

    async def get_movie_by_tmdb_id(self, tmdb_id: int) -> RadarrMovieResource | None:
        response = await self._request(
            "GET",
            "/api/v3/movie",
            params={"tmdbId": tmdb_id},
            operation="movie lookup by tmdb id",
            allowed_status_codes={200, 404},
        )
        if response.status_code == 404:
            return None

        payload = self._json(response=response, operation="movie lookup by tmdb id")
        return self._extract_movie_resource_matching(
            payload,
            matches=lambda movie: movie.tmdb_id == tmdb_id,
            error_context=f"tmdb_id={tmdb_id}",
        )

    async def get_movie_by_imdb_id(self, imdb_id: str) -> RadarrMovieResource | None:
        response = await self._request(
            "GET",
            "/api/v3/movie",
            params={"imdbId": imdb_id},
            operation="movie lookup by imdb id",
            allowed_status_codes={200, 404},
        )
        if response.status_code == 404:
            return None

        payload = self._json(response=response, operation="movie lookup by imdb id")
        return self._extract_movie_resource_matching(
            payload,
            matches=lambda movie: movie.imdb_id == imdb_id,
            error_context=f"imdb_id={imdb_id}",
        )

    async def lookup_movie_by_tmdb_id(self, tmdb_id: int) -> RadarrMovieLookupItem | None:
        response = await self._request(
            "GET",
            "/api/v3/movie/lookup/tmdb",
            params={"tmdbId": tmdb_id},
            operation="movie lookup metadata by tmdb id",
            allowed_status_codes={200, 400, 404},
        )
        if response.status_code == 200:
            payload = self._json(response=response, operation="movie lookup metadata by tmdb id")
            movie = self._extract_movie_lookup_matching(
                payload,
                matches=lambda item: item.tmdb_id == tmdb_id,
                error_context=f"tmdb_id={tmdb_id}",
            )
            if movie is not None:
                return movie

        return await self._lookup_movie_by_term(
            term=f"tmdb:{tmdb_id}",
            matches=lambda item: item.tmdb_id == tmdb_id,
            error_context=f"tmdb_id={tmdb_id}",
        )

    async def lookup_movie_by_imdb_id(self, imdb_id: str) -> RadarrMovieLookupItem | None:
        response = await self._request(
            "GET",
            "/api/v3/movie/lookup/imdb",
            params={"imdbId": imdb_id},
            operation="movie lookup metadata by imdb id",
            allowed_status_codes={200, 400, 404},
        )
        if response.status_code == 200:
            payload = self._json(response=response, operation="movie lookup metadata by imdb id")
            movie = self._extract_movie_lookup_matching(
                payload,
                matches=lambda item: item.imdb_id == imdb_id,
                error_context=f"imdb_id={imdb_id}",
            )
            if movie is not None:
                return movie

        return await self._lookup_movie_by_term(
            term=f"imdb:{imdb_id}",
            matches=lambda item: item.imdb_id == imdb_id,
            error_context=f"imdb_id={imdb_id}",
        )

    async def get_quality_profiles(self) -> list[RadarrQualityProfile]:
        response = await self._request(
            "GET",
            "/api/v3/qualityprofile",
            operation="quality profile lookup",
        )
        payload = self._json(response=response, operation="quality profile lookup")
        try:
            return RadarrQualityProfileResponse.model_validate(payload).root
        except ValidationError as exc:
            logger.error(
                "Radarr quality profile response validation failed error_count=%s",
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc

    async def add_movie_by_tmdb_id(
        self,
        *,
        tmdb_id: int,
        title: str,
        year: int,
        quality_profile_id: int,
    ) -> tuple[RadarrMovieResource, bool]:
        lookup_payload = await self._lookup_movie_payload(tmdb_id=tmdb_id)
        root_folder_path = await self._get_default_root_folder_path()

        add_payload = {
            **lookup_payload,
            "title": lookup_payload.get("title") or title,
            "year": lookup_payload.get("year") or year,
            "tmdbId": tmdb_id,
            "titleSlug": lookup_payload.get("titleSlug")
            or self._build_title_slug(title=title, tmdb_id=tmdb_id),
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": True,
            "minimumAvailability": lookup_payload.get("minimumAvailability") or "released",
            "addOptions": {"searchForMovie": True},
        }

        response = await self._request(
            "POST",
            "/api/v3/movie",
            json=add_payload,
            operation="movie add",
            allowed_status_codes={200, 201, 202, 400, 409},
        )
        if response.status_code in {400, 409}:
            existing = await self.get_movie_by_tmdb_id(tmdb_id)
            if existing is not None:
                return existing, False
            raise UpstreamServiceError(message="Radarr 添加电影请求失败")

        payload = self._json(response=response, operation="movie add")
        try:
            movie = RadarrMovieResource.model_validate(payload)
        except ValidationError as exc:
            logger.error(
                "Radarr add response validation failed for tmdb_id=%s error_count=%s",
                tmdb_id,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc

        if movie.id is not None:
            return movie, True

        existing = await self.get_movie_by_tmdb_id(tmdb_id)
        if existing is not None:
            return existing, True
        raise InvalidUpstreamResponseError()

    async def update_movie_quality_profile(
        self,
        *,
        movie: RadarrMovieResource,
        quality_profile_id: int,
    ) -> RadarrMovieResource:
        if movie.id is None:
            raise InvalidUpstreamResponseError()

        update_payload = (
            dict(movie.raw_payload)
            if movie.raw_payload
            else movie.model_dump(by_alias=True, exclude_none=True)
        )
        update_payload["qualityProfileId"] = quality_profile_id

        response = await self._request(
            "PUT",
            f"/api/v3/movie/{movie.id}",
            json=update_payload,
            operation="movie update quality profile",
            allowed_status_codes={200, 202},
        )
        payload = self._json(response=response, operation="movie update quality profile")
        try:
            updated_movie = RadarrMovieResource.model_validate(payload)
        except ValidationError as exc:
            logger.error(
                "Radarr movie update response validation failed for movie_id=%s error_count=%s",
                movie.id,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc

        if updated_movie.id is not None:
            return updated_movie
        if movie.tmdb_id is not None:
            refreshed_movie = await self.get_movie_by_tmdb_id(movie.tmdb_id)
            if refreshed_movie is not None:
                return refreshed_movie
        raise InvalidUpstreamResponseError()

    async def start_movie_search(self, movie_id: int) -> None:
        await self._request(
            "POST",
            "/api/v3/command",
            json={"name": "MoviesSearch", "movieIds": [movie_id]},
            operation="movie search command",
            allowed_status_codes={200, 201, 202},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        allowed_status_codes: set[int] | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        allowed_status_codes = allowed_status_codes or {200}

        try:
            async with httpx.AsyncClient(timeout=self.settings.radarr_timeout) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=self._build_headers(),
                )
        except httpx.TimeoutException as exc:
            logger.warning("Radarr %s request timed out", operation)
            raise UpstreamServiceUnavailable() from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Radarr %s request error error_type=%s",
                operation,
                exc.__class__.__name__,
            )
            raise UpstreamServiceUnavailable() from exc

        if response.status_code not in allowed_status_codes:
            logger.warning(
                "Radarr %s failed status_code=%s",
                operation,
                response.status_code,
            )
            raise UpstreamServiceError()

        return response

    def _json(self, *, response: httpx.Response, operation: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            logger.error("Radarr returned invalid JSON for %s", operation)
            raise InvalidUpstreamResponseError() from exc

    async def _lookup_movie_payload(self, *, tmdb_id: int) -> dict[str, Any]:
        response = await self._request(
            "GET",
            "/api/v3/movie/lookup/tmdb",
            params={"tmdbId": tmdb_id},
            operation="movie lookup by tmdb id",
            allowed_status_codes={200, 400, 404},
        )
        if response.status_code in {400, 404}:
            return await self._lookup_movie_payload_by_term(tmdb_id=tmdb_id)

        payload = self._json(response=response, operation="movie lookup by tmdb id")
        return self._extract_lookup_payload(payload, tmdb_id=tmdb_id)

    async def _lookup_movie_payload_by_term(self, *, tmdb_id: int) -> dict[str, Any]:
        response = await self._request(
            "GET",
            "/api/v3/movie/lookup",
            params={"term": f"tmdb:{tmdb_id}"},
            operation="movie lookup by tmdb term",
        )
        payload = self._json(response=response, operation="movie lookup by tmdb term")
        return self._extract_lookup_payload(payload, tmdb_id=tmdb_id)

    def _extract_lookup_payload(self, payload: Any, *, tmdb_id: int) -> dict[str, Any]:
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and self._has_tmdb_id(item, tmdb_id=tmdb_id):
                    return item
            raise InvalidUpstreamResponseError()
        if isinstance(payload, dict) and self._has_tmdb_id(payload, tmdb_id=tmdb_id):
            return payload
        raise InvalidUpstreamResponseError()

    async def _get_default_root_folder_path(self) -> str:
        response = await self._request(
            "GET",
            "/api/v3/rootfolder",
            operation="root folder lookup",
        )
        payload = self._json(response=response, operation="root folder lookup")
        try:
            root_folders = RadarrRootFolderResponse.model_validate(payload).root
        except ValidationError as exc:
            logger.error(
                "Radarr root folder response validation failed error_count=%s",
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc

        for root_folder in root_folders:
            if root_folder.path:
                return root_folder.path
        raise UpstreamServiceError(message="Radarr 根目录未配置")

    async def _get_default_quality_profile_id(self) -> int:
        quality_profiles = await self.get_quality_profiles()

        for quality_profile in quality_profiles:
            if quality_profile.id is not None:
                return quality_profile.id
        raise UpstreamServiceError(message="Radarr 质量配置未配置")

    async def _lookup_movie_by_term(
        self,
        *,
        term: str,
        matches: Callable[[RadarrMovieLookupItem], bool],
        error_context: str,
    ) -> RadarrMovieLookupItem | None:
        response = await self._request(
            "GET",
            "/api/v3/movie/lookup",
            params={"term": term},
            operation="movie lookup by identifier term",
        )
        payload = self._json(response=response, operation="movie lookup by identifier term")
        return self._extract_movie_lookup_matching(
            payload,
            matches=matches,
            error_context=error_context,
        )

    def _extract_movie_resource_matching(
        self,
        payload: Any,
        *,
        matches: Callable[[RadarrMovieResource], bool],
        error_context: str,
    ) -> RadarrMovieResource | None:
        try:
            if isinstance(payload, list):
                movies = RadarrMovieResourceResponse.model_validate(payload).root
                for movie in movies:
                    if matches(movie):
                        return movie
                return None
            if isinstance(payload, dict):
                movie = RadarrMovieResource.model_validate(payload)
                if matches(movie):
                    return movie
                return None
        except ValidationError as exc:
            logger.error(
                "Radarr movie response validation failed for %s error_count=%s",
                error_context,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc
        raise InvalidUpstreamResponseError()

    def _extract_movie_lookup_matching(
        self,
        payload: Any,
        *,
        matches: Callable[[RadarrMovieLookupItem], bool],
        error_context: str,
    ) -> RadarrMovieLookupItem | None:
        try:
            if isinstance(payload, list):
                movies = RadarrMovieLookupResponse.model_validate(payload).root
                for movie in movies:
                    if matches(movie):
                        return movie
                return None
            if isinstance(payload, dict):
                movie = RadarrMovieLookupItem.model_validate(payload)
                if matches(movie):
                    return movie
                return None
        except ValidationError as exc:
            logger.error(
                "Radarr movie lookup response validation failed for %s error_count=%s",
                error_context,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc
        raise InvalidUpstreamResponseError()

    def _build_title_slug(self, *, title: str, tmdb_id: int) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
        return slug or f"movie-{tmdb_id}"

    def _has_tmdb_id(self, payload: dict[str, Any], *, tmdb_id: int) -> bool:
        try:
            return int(payload.get("tmdbId")) == tmdb_id
        except (TypeError, ValueError):
            return False
