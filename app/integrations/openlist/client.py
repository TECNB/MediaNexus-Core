import asyncio
import logging
import posixpath
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException

logger = logging.getLogger("app.integrations.openlist")


class OpenListClient:
    AUTH_ERROR_KEYWORDS = (
        "token expired",
        "token invalid",
        "token 无效",
        "token已过期",
        "token 失效",
        "unauthorized",
    )
    NOT_FOUND_KEYWORDS = (
        "not found",
        "does not exist",
        "object not found",
        "file not found",
        "目录不存在",
        "路径不存在",
    )
    ALREADY_EXISTS_KEYWORDS = (
        "already exists",
        "file exists",
        "目录已存在",
        "路径已存在",
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._token: str | None = None

    @property
    def base_url(self) -> str:
        host = (self.settings.alist_host or "").strip().rstrip("/")
        if not host:
            raise AppException(status_code=503, message="OpenList 服务尚未配置")
        return host

    async def login(self) -> str:
        username = (self.settings.alist_username or "").strip()
        password = (self.settings.alist_password or "").strip()
        if not username or not password:
            raise AppException(status_code=503, message="OpenList 服务尚未配置")

        response, payload = await self._post(
            endpoint="/api/auth/login",
            json_body={"username": username, "password": password},
            include_auth=False,
        )

        if response.status_code >= 400:
            logger.warning("OpenList login failed with status_code=%s", response.status_code)
            raise AppException(status_code=502, message="OpenList 登录失败")

        if not self._is_success_payload(payload):
            logger.warning("OpenList login returned non-success payload")
            raise AppException(status_code=502, message="OpenList 登录失败")

        token = self._extract_data(payload).get("token")
        if not token or not isinstance(token, str):
            logger.warning("OpenList login response missing token")
            raise AppException(status_code=502, message="OpenList 登录失败")

        self._token = token
        return token

    async def post_with_retry(
        self,
        endpoint: str,
        json_body: dict[str, Any],
        *,
        include_auth: bool = True,
    ) -> tuple[httpx.Response, dict[str, Any]]:
        response, payload = await self._post(endpoint=endpoint, json_body=json_body, include_auth=include_auth)

        if include_auth and self._should_retry_for_auth(response=response, payload=payload):
            logger.info("OpenList token expired, retrying endpoint=%s", endpoint)
            self._token = None
            await self.login()
            response, payload = await self._post(
                endpoint=endpoint,
                json_body=json_body,
                include_auth=include_auth,
            )

        return response, payload

    async def path_exists(self, path: str) -> bool:
        response, payload = await self.post_with_retry(
            endpoint="/api/fs/get",
            json_body={"path": self._normalize_path(path)},
        )

        if response.status_code == 404:
            return False

        if response.status_code >= 400:
            raise AppException(status_code=502, message="检查 OpenList 目录状态失败")

        if self._is_success_payload(payload):
            return True

        if self._is_not_found_payload(payload):
            return False

        raise AppException(status_code=502, message="检查 OpenList 目录状态失败")

    async def mkdir(self, path: str) -> None:
        response, payload = await self.post_with_retry(
            endpoint="/api/fs/mkdir",
            json_body={"path": self._normalize_path(path)},
        )

        if response.status_code >= 400:
            raise AppException(status_code=502, message="创建 OpenList 目录失败")

        if self._is_success_payload(payload) or self._is_already_exists_payload(payload):
            return

        raise AppException(status_code=502, message="创建 OpenList 目录失败")

    async def refresh_path(self, path: str) -> None:
        normalized_path = self._normalize_path(path)

        try:
            response, payload = await self.post_with_retry(
                endpoint="/api/fs/list",
                json_body={
                    "path": normalized_path,
                    "password": "",
                    "page": 1,
                    "per_page": 1,
                    "refresh": True,
                },
            )
        except AppException:
            logger.warning("OpenList refresh path failed path=%s", normalized_path)
            return

        if response.status_code >= 400 or not self._is_success_payload(payload):
            logger.warning("OpenList refresh path returned non-success path=%s", normalized_path)

    async def ensure_path_ready(self, full_path: str, skip_prefix_path: str) -> None:
        normalized_full_path = self._normalize_path(full_path)
        normalized_prefix_path = self._normalize_path(skip_prefix_path)

        if not await self.path_exists(normalized_prefix_path):
            raise AppException(status_code=503, message="OpenList 电影基础路径不存在")

        if normalized_full_path == normalized_prefix_path:
            return

        prefix_with_slash = normalized_prefix_path.rstrip("/") + "/"
        if not normalized_full_path.startswith(prefix_with_slash):
            raise AppException(status_code=500, message="OpenList 路径配置无效")

        if await self.path_exists(normalized_full_path):
            return

        current_path = normalized_prefix_path
        relative_path = normalized_full_path[len(prefix_with_slash) :]

        for segment in [item for item in relative_path.split("/") if item]:
            current_path = self._join_path(current_path, segment)
            if await self.path_exists(current_path):
                continue

            await self.mkdir(current_path)
            await self.refresh_path(self._parent_path(current_path))

            if not await self._wait_until_path_exists(current_path):
                raise AppException(status_code=502, message="OpenList 目标目录创建失败")

    async def add_offline_download(self, path: str, magnet: str) -> None:
        response, payload = await self.post_with_retry(
            endpoint="/api/fs/add_offline_download",
            json_body={
                "path": self._normalize_path(path),
                "urls": [magnet],
                "tool": "PikPak",
                "delete_policy": "delete_on_upload_succeed",
            },
        )

        if response.status_code >= 400 or not self._is_success_payload(payload):
            raise AppException(status_code=502, message="OpenList 离线下载任务创建失败")

    async def _wait_until_path_exists(self, path: str, *, attempts: int = 3, delay_seconds: float = 0.3) -> bool:
        for index in range(attempts):
            if await self.path_exists(path):
                return True
            if index < attempts - 1:
                await asyncio.sleep(delay_seconds)
        return False

    async def _post(
        self,
        *,
        endpoint: str,
        json_body: dict[str, Any],
        include_auth: bool,
    ) -> tuple[httpx.Response, dict[str, Any]]:
        headers = {"Content-Type": "application/json"}
        if include_auth:
            if not self._token:
                await self.login()
            headers["Authorization"] = self._token or ""

        try:
            async with httpx.AsyncClient(timeout=self.settings.alist_timeout) as client:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=json_body,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            logger.warning("OpenList request timed out endpoint=%s", endpoint)
            raise AppException(status_code=503, message="OpenList 服务暂时不可用") from exc
        except httpx.RequestError as exc:
            logger.warning("OpenList request error endpoint=%s error_type=%s", endpoint, exc.__class__.__name__)
            raise AppException(status_code=503, message="OpenList 服务暂时不可用") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if isinstance(payload, dict):
            return response, payload
        return response, {}

    def _should_retry_for_auth(self, *, response: httpx.Response, payload: dict[str, Any]) -> bool:
        if response.status_code == 401:
            return True

        if self._is_success_payload(payload):
            return False

        return self._contains_keyword(self._extract_message(payload), self.AUTH_ERROR_KEYWORDS)

    def _is_success_payload(self, payload: dict[str, Any]) -> bool:
        return payload.get("code") == 200

    def _is_not_found_payload(self, payload: dict[str, Any]) -> bool:
        return self._contains_keyword(self._extract_message(payload), self.NOT_FOUND_KEYWORDS)

    def _is_already_exists_payload(self, payload: dict[str, Any]) -> bool:
        return self._contains_keyword(self._extract_message(payload), self.ALREADY_EXISTS_KEYWORDS)

    def _extract_message(self, payload: dict[str, Any]) -> str:
        for key in ("message", "msg"):
            value = payload.get(key)
            if isinstance(value, str):
                return value.strip().lower()
        return ""

    def _extract_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return {}

    def _contains_keyword(self, message: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in message for keyword in keywords)

    def _normalize_path(self, path: str) -> str:
        normalized_path = posixpath.normpath((path or "").strip())
        if not normalized_path or normalized_path == ".":
            return "/"
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path.lstrip('/')}"
        return normalized_path

    def _join_path(self, base_path: str, segment: str) -> str:
        return self._normalize_path(posixpath.join(base_path, segment))

    def _parent_path(self, path: str) -> str:
        parent_path = posixpath.dirname(self._normalize_path(path))
        return parent_path or "/"
