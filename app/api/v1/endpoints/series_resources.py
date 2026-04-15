from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import AppException
from app.core.response import success_response
from app.schemas.common import APIResponse
from app.schemas.resources import SeriesSearchResult, SeriesSeasonsResponseData
from app.services.series_search import SeriesSearchService

router = APIRouter(prefix="/resources/series", tags=["resources"])


def get_series_search_service() -> SeriesSearchService:
    return SeriesSearchService()


@router.get("/search", response_model=APIResponse[SeriesSearchResult])
async def search_series(
    service: Annotated[SeriesSearchService, Depends(get_series_search_service)],
    term: Annotated[str | None, Query(description="Series keyword used to search in Sonarr")] = None,
) -> APIResponse[SeriesSearchResult]:
    normalized_term = (term or "").strip()
    if not normalized_term:
        raise AppException(status_code=400, message="搜索关键词不能为空")

    result = await service.search_series(normalized_term)
    return success_response(data=result)


@router.get("/seasons", response_model=APIResponse[SeriesSeasonsResponseData])
async def get_series_seasons(
    service: Annotated[SeriesSearchService, Depends(get_series_search_service)],
    tvdb_id: Annotated[int | None, Query(description="TVDB id used to lookup seasons in Sonarr")] = None,
) -> APIResponse[SeriesSeasonsResponseData]:
    if tvdb_id is None:
        raise AppException(status_code=400, message="tvdb_id is required")
    if tvdb_id <= 0:
        raise AppException(status_code=400, message="tvdb_id must be greater than 0")

    result = await service.get_series_seasons(tvdb_id)
    return success_response(data=result)
