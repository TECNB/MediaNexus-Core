import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import error_response

logger = logging.getLogger("app.exceptions")


class AppException(Exception):
    def __init__(self, *, status_code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.data = data


class UpstreamServiceUnavailable(AppException):
    def __init__(self, message: str = "Radarr 服务暂时不可用", data: Any = None) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=message,
            data=data,
        )


class UpstreamServiceError(AppException):
    def __init__(self, message: str = "Radarr 搜索请求失败", data: Any = None) -> None:
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, message=message, data=data)


class InvalidUpstreamResponseError(AppException):
    def __init__(self, message: str = "Radarr 返回了无法解析的数据", data: Any = None) -> None:
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, message=message, data=data)


def _build_error_response(message: str, data: Any = None) -> dict[str, Any]:
    return error_response(message=message, data=data).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning("Application exception on %s %s: %s", request.method, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_response(message=exc.message, data=exc.data),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning("HTTP exception on %s %s: %s", request.method, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_response(message=str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_build_error_response(
                message="Validation error",
                data={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error_response(message="Internal server error"),
        )
