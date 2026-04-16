from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import ValidationError

from app.core.exceptions import AppException
from app.core.response import success_response
from app.schemas.common import APIResponse
from app.schemas.resources import (
    MovieAddRequest,
    MovieAddResult,
    MovieQualityProfilesResult,
    MovieSearchResult,
)
from app.services.movie_add import MovieAddService
from app.services.movie_quality_profiles import MovieQualityProfileService
from app.services.resource_search import MovieSearchService

router = APIRouter(prefix="/resources/movies", tags=["resources"])


def get_movie_search_service() -> MovieSearchService:
    return MovieSearchService()


def get_movie_add_service() -> MovieAddService:
    return MovieAddService()


def get_movie_quality_profile_service() -> MovieQualityProfileService:
    return MovieQualityProfileService()


@router.get("/search", response_model=APIResponse[MovieSearchResult])
async def search_movies(
    term: Annotated[str, Query(description="Movie keyword used to search in Radarr")],
    service: Annotated[MovieSearchService, Depends(get_movie_search_service)],
) -> APIResponse[MovieSearchResult]:
    normalized_term = term.strip()
    if not normalized_term:
        raise AppException(status_code=400, message="搜索关键词不能为空")

    result = await service.search_movies(normalized_term)
    return success_response(data=result)


@router.get("/quality-profiles", response_model=APIResponse[MovieQualityProfilesResult])
async def get_quality_profiles(
    service: Annotated[
        MovieQualityProfileService,
        Depends(get_movie_quality_profile_service),
    ],
) -> APIResponse[MovieQualityProfilesResult]:
    result = await service.get_quality_profiles()
    return success_response(data=result)


@router.post("/add", response_model=APIResponse[MovieAddResult])
async def add_movie(
    service: Annotated[MovieAddService, Depends(get_movie_add_service)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> APIResponse[MovieAddResult]:
    try:
        request = MovieAddRequest.model_validate(body)
    except ValidationError as exc:
        raise AppException(status_code=400, message="invalid movie add parameters") from exc

    result = await service.add_and_search_movie(request)
    message = (
        "movie added and search started"
        if result.action == "added_then_searched"
        else "existing movie updated and search started"
    )
    return success_response(data=result, message=message)
