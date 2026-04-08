from typing import Any, TypeVar

from app.schemas.common import APIResponse

T = TypeVar("T")


def success_response(data: T | None = None, message: str = "ok") -> APIResponse[T]:
    return APIResponse[T](success=True, message=message, data=data)


def error_response(message: str = "error", data: Any = None) -> APIResponse[Any]:
    return APIResponse[Any](success=False, message=message, data=data)
