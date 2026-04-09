from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.resources import router as resources_router
from app.api.v1.endpoints.series_resources import router as series_resources_router

router = APIRouter()
router.include_router(health_router)
router.include_router(resources_router)
router.include_router(series_resources_router)
