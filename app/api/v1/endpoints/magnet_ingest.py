from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.response import success_response
from app.schemas.common import APIResponse
from app.schemas.magnet_ingest import (
    MagnetIngestMovieRequest,
    MagnetIngestMovieResult,
    SeriesMagnetIngestRequest,
    SeriesMagnetIngestResult,
)
from app.services.magnet_ingest_service import MagnetIngestService

router = APIRouter(prefix="/magnet-ingest", tags=["magnet-ingest"])


def get_magnet_ingest_service() -> MagnetIngestService:
    return MagnetIngestService()


@router.post("/movies", response_model=APIResponse[MagnetIngestMovieResult])
async def ingest_movie_magnet(
    request: MagnetIngestMovieRequest,
    service: Annotated[MagnetIngestService, Depends(get_magnet_ingest_service)],
) -> APIResponse[MagnetIngestMovieResult]:
    result = await service.ingest_movie(request)
    return success_response(data=result, message="offline task created")


@router.post("/series", response_model=APIResponse[SeriesMagnetIngestResult])
async def ingest_series_magnet(
    request: SeriesMagnetIngestRequest,
    service: Annotated[MagnetIngestService, Depends(get_magnet_ingest_service)],
) -> APIResponse[SeriesMagnetIngestResult]:
    result = await service.ingest_series(request)
    return success_response(data=result, message="offline task created")
