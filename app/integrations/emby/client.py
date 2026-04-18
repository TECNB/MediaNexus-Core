import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.integrations.emby")


class EmbyClientError(Exception):
    """Raised when Emby refresh operations fail."""


@dataclass(frozen=True)
class EmbyItemMatch:
    item_id: str
    path: str


class EmbyClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def is_enabled(self) -> bool:
        return bool((self.settings.emby_url or "").strip() and (self.settings.emby_api_key or "").strip())

    @property
    def base_url(self) -> str:
        raw_url = (self.settings.emby_url or "").strip().rstrip("/")
        if not raw_url:
            raise EmbyClientError("emby url is not configured")
        if raw_url.endswith("/emby"):
            return raw_url
        return f"{raw_url}/emby"

    def refresh_media_paths(self, media_paths: list[str]) -> None:
        normalized_paths = self._deduplicate_paths(
            self._map_path_for_emby(path) for path in media_paths if path.strip()
        )
        if not normalized_paths:
            return

        unresolved_paths: list[str] = []
        refreshed_item_ids: list[str] = []

        for media_path in normalized_paths:
            item_match = self.find_item_by_path(media_path)
            if item_match is None:
                unresolved_paths.append(media_path)
                continue

            self.refresh_item(item_match.item_id)
            refreshed_item_ids.append(item_match.item_id)

        if unresolved_paths:
            self.report_media_updated(unresolved_paths)

        logger.info(
            "Emby refresh completed refreshed_items=%s fallback_paths=%s",
            len(refreshed_item_ids),
            len(unresolved_paths),
        )

    def find_item_by_path(self, media_path: str) -> EmbyItemMatch | None:
        response = self._request(
            "GET",
            "/Items",
            params={
                "Recursive": "true",
                "Fields": "Path",
                "IncludeItemTypes": "Movie,Episode",
                "Path": media_path,
            },
            operation="item lookup by path",
        )
        payload = self._json(response=response, operation="item lookup by path")
        items = payload.get("Items")
        if not isinstance(items, list):
            raise EmbyClientError("emby item lookup returned invalid payload")

        for item in items:
            item_id = item.get("Id")
            item_path = item.get("Path")
            if isinstance(item_id, str) and item_path == media_path:
                return EmbyItemMatch(item_id=item_id, path=item_path)

        return None

    def refresh_item(self, item_id: str) -> None:
        self._request(
            "POST",
            f"/Items/{item_id}/Refresh",
            json={},
            operation=f"item refresh {item_id}",
            allowed_status_codes={200, 204},
        )

    def report_media_updated(self, media_paths: list[str]) -> None:
        updates = [{"Path": media_path, "UpdateType": "Modified"} for media_path in media_paths]
        self._request(
            "POST",
            "/Library/Media/Updated",
            json={"Updates": updates},
            operation="library media updated",
            allowed_status_codes={200, 204},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        allowed_status_codes: set[int] | None = None,
    ) -> httpx.Response:
        if not self.is_enabled:
            raise EmbyClientError("emby is not configured")

        allowed_status_codes = allowed_status_codes or {200}
        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(timeout=self.settings.emby_timeout) as client:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=self._build_headers(),
                )
        except httpx.TimeoutException as exc:
            logger.warning("Emby %s timed out", operation)
            raise EmbyClientError("emby request timed out") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Emby %s request error error_type=%s",
                operation,
                exc.__class__.__name__,
            )
            raise EmbyClientError("emby request failed") from exc

        if response.status_code not in allowed_status_codes:
            logger.warning(
                "Emby %s failed status_code=%s",
                operation,
                response.status_code,
            )
            raise EmbyClientError("emby request failed")

        return response

    def _json(self, *, response: httpx.Response, operation: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            logger.warning("Emby %s returned invalid json", operation)
            raise EmbyClientError("emby returned invalid json") from exc

    def _build_headers(self) -> dict[str, str]:
        api_key = (self.settings.emby_api_key or "").strip()
        if not api_key:
            raise EmbyClientError("emby api key is not configured")
        return {
            "Content-Type": "application/json",
            "X-Emby-Token": api_key,
        }

    def _map_path_for_emby(self, path: str) -> str:
        normalized_path = path.strip().replace("\\", "/")
        prefix_from = (self.settings.emby_path_prefix_from or "").strip().rstrip("/")
        prefix_to = (self.settings.emby_path_prefix_to or "").strip().rstrip("/")

        if prefix_from and prefix_to and (
            normalized_path == prefix_from or normalized_path.startswith(f"{prefix_from}/")
        ):
            suffix = normalized_path[len(prefix_from) :]
            return f"{prefix_to}{suffix}" or prefix_to

        return normalized_path

    def _deduplicate_paths(self, paths: Any) -> list[str]:
        unique_paths: list[str] = []
        seen_paths: set[str] = set()

        for path in paths:
            if not isinstance(path, str):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            unique_paths.append(path)

        return unique_paths
