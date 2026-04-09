import logging
import re
from time import perf_counter

from app.core.exceptions import AppException
from app.integrations.sonarr.client import SonarrClient
from app.integrations.sonarr.schemas import SonarrSeriesImage, SonarrSeriesLookupItem
from app.schemas.resources import SeriesSearchItem, SeriesSearchResult

logger = logging.getLogger("app.services.series_search")


class SeriesSearchService:
    def __init__(self, sonarr_client: SonarrClient | None = None) -> None:
        self.sonarr_client = sonarr_client or SonarrClient()

    async def search_series(self, term: str) -> SeriesSearchResult:
        started_at = perf_counter()
        success = False
        result_count = 0
        error_type = "none"

        try:
            series_list = await self.sonarr_client.search_series(term=term)
            items = [self._map_series(series) for series in series_list]
            result_count = len(items)
            success = True
            return SeriesSearchResult(items=items)
        except AppException as exc:
            error_type = exc.__class__.__name__
            raise
        except Exception as exc:
            error_type = exc.__class__.__name__
            logger.exception("Unexpected series search error for term=%r", term)
            raise
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Series search completed term=%r success=%s results=%s duration_ms=%.2f error_type=%s",
                term,
                success,
                result_count,
                duration_ms,
                error_type,
            )

    def _map_series(self, series: SonarrSeriesLookupItem) -> SeriesSearchItem:
        title = (series.title or "").strip() or "Unknown Title"
        return SeriesSearchItem(
            id=self._build_series_id(series, title=title),
            title=title,
            original_title=(series.original_title or "").strip() or None,
            year=series.year,
            overview=(series.overview or "").strip(),
            poster=self._extract_poster(series.images),
            tvdb_id=series.tvdb_id,
            imdb_id=series.imdb_id,
            tmdb_id=series.tmdb_id,
            status=self._normalize_status(series.status),
            network=(series.network or "").strip() or None,
            series_type=(series.series_type or "").strip() or None,
        )

    def _build_series_id(self, series: SonarrSeriesLookupItem, *, title: str) -> str:
        if series.tvdb_id is not None:
            return f"tvdb:{series.tvdb_id}"
        if series.tmdb_id is not None:
            return f"tmdb:{series.tmdb_id}"
        if series.imdb_id:
            return f"imdb:{series.imdb_id}"
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or "unknown"
        safe_year = str(series.year) if series.year is not None else "unknown"
        return f"{safe_title}-{safe_year}"

    def _extract_poster(self, images: list[SonarrSeriesImage]) -> str | None:
        for image in images:
            if (image.cover_type or "").lower() == "poster":
                return image.remote_url or image.url
        return None

    def _normalize_status(self, value: str | None) -> str:
        if not value:
            return "unknown"
        return value.strip().lower() or "unknown"
