import logging

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    InvalidUpstreamResponseError,
    UpstreamServiceError,
    UpstreamServiceUnavailable,
)
from app.integrations.radarr.schemas import RadarrMovieLookupItem, RadarrMovieLookupResponse

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
        url = f"{self.base_url}/api/v3/movie/lookup"

        try:
            async with httpx.AsyncClient(timeout=self.settings.radarr_timeout) as client:
                response = await client.get(
                    url,
                    params={"term": term},
                    headers=self._build_headers(),
                )
        except httpx.TimeoutException as exc:
            logger.warning("Radarr request timed out for term=%r", term)
            raise UpstreamServiceUnavailable() from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Radarr request error for term=%r error_type=%s",
                term,
                exc.__class__.__name__,
            )
            raise UpstreamServiceUnavailable() from exc

        if response.status_code >= 400:
            logger.warning(
                "Radarr search failed for term=%r status_code=%s",
                term,
                response.status_code,
            )
            raise UpstreamServiceError()

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("Radarr returned invalid JSON for term=%r", term)
            raise InvalidUpstreamResponseError() from exc

        try:
            return RadarrMovieLookupResponse.model_validate(payload).root
        except ValidationError as exc:
            logger.error(
                "Radarr response validation failed for term=%r error_count=%s",
                term,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError() from exc
