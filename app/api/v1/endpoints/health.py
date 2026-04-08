from fastapi import APIRouter

from app.core.config import get_settings
from app.core.response import success_response
from app.schemas.common import APIResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=APIResponse[dict[str, str]])
def health_check() -> APIResponse[dict[str, str]]:
    settings = get_settings()
    data = {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }
    return success_response(data=data)


@router.get("/ping", response_model=APIResponse[dict[str, str]])
def ping() -> APIResponse[dict[str, str]]:
    return success_response(data={"status": "ok", "result": "pong"})
