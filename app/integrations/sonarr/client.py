import logging

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    InvalidUpstreamResponseError,
    UpstreamServiceError,
    UpstreamServiceUnavailable,
)
from app.integrations.sonarr.schemas import SonarrSeriesLookupItem, SonarrSeriesLookupResponse

logger = logging.getLogger("app.integrations.sonarr")


class SonarrClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def base_url(self) -> str:
        host = (self.settings.sonarr_host or "").strip().rstrip("/")
        if not host:
            raise UpstreamServiceUnavailable(message="Sonarr 服务尚未配置")

        base_url = f"{self.settings.sonarr_scheme}://{host}"
        if self.settings.sonarr_port is not None:
            base_url = f"{base_url}:{self.settings.sonarr_port}"
        return base_url

    def _build_headers(self) -> dict[str, str]:
        if not self.settings.sonarr_api_key:
            raise UpstreamServiceUnavailable(message="Sonarr 服务尚未配置")
        return {"X-Api-Key": self.settings.sonarr_api_key}

    async def search_series(self, term: str) -> list[SonarrSeriesLookupItem]:
        return await self._lookup_series(term=term)

    async def get_series_by_tvdb_id(self, tvdb_id: int) -> SonarrSeriesLookupItem | None:
        series_list = await self._lookup_series(term=f"tvdb:{tvdb_id}")
        for series in series_list:
            if series.tvdb_id == tvdb_id:
                return series
        return None

    async def _lookup_series(self, term: str) -> list[SonarrSeriesLookupItem]:
        url = f"{self.base_url}/api/v3/series/lookup"

        try:
            async with httpx.AsyncClient(timeout=self.settings.sonarr_timeout) as client:
                response = await client.get(
                    url,
                    params={"term": term},
                    headers=self._build_headers(),
                )
        except httpx.TimeoutException as exc:
            logger.warning("Sonarr request timed out for term=%r", term)
            raise UpstreamServiceUnavailable(message="Sonarr 服务暂时不可用") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Sonarr request error for term=%r error_type=%s",
                term,
                exc.__class__.__name__,
            )
            raise UpstreamServiceUnavailable(message="Sonarr 服务暂时不可用") from exc

        if response.status_code >= 400:
            logger.warning(
                "Sonarr search failed for term=%r status_code=%s",
                term,
                response.status_code,
            )
            raise UpstreamServiceError(message="Sonarr 搜索请求失败")

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("Sonarr returned invalid JSON for term=%r", term)
            raise InvalidUpstreamResponseError(message="Sonarr 返回了无法解析的数据") from exc

        try:
            return SonarrSeriesLookupResponse.model_validate(payload).root
        except ValidationError as exc:
            logger.error(
                "Sonarr response validation failed for term=%r error_count=%s",
                term,
                len(exc.errors()),
            )
            raise InvalidUpstreamResponseError(message="Sonarr 返回了无法解析的数据") from exc
