from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import AppException
from app.core.response import success_response
from app.schemas.common import APIResponse
from app.schemas.resources import MovieSearchResult
from app.services.resource_search import MovieSearchService

router = APIRouter(prefix="/resources/movies", tags=["resources"])


def get_movie_search_service() -> MovieSearchService:
    return MovieSearchService()


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
