from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.magnet_ingest import router as magnet_ingest_router
from app.api.v1.endpoints.resources import router as resources_router
from app.api.v1.endpoints.series_resources import router as series_resources_router
from app.api.v1.endpoints.subtitles import router as subtitles_router

router = APIRouter()
router.include_router(health_router)
router.include_router(magnet_ingest_router)
router.include_router(resources_router)
router.include_router(series_resources_router)
router.include_router(subtitles_router)
