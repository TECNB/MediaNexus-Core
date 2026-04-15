import logging
import posixpath
import re
from time import perf_counter

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.integrations.openlist.client import OpenListClient
from app.schemas.magnet_ingest import MagnetIngestMovieRequest, MagnetIngestMovieResult

logger = logging.getLogger("app.services.magnet_ingest")


class MagnetIngestService:
    INVALID_PATH_CHAR_PATTERN = re.compile(r'[\\/:\*\?"<>\|]+')
    MULTIPLE_SPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        settings: Settings | None = None,
        openlist_client: OpenListClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.openlist_client = openlist_client or OpenListClient(settings=self.settings)

    async def ingest_movie(self, request: MagnetIngestMovieRequest) -> MagnetIngestMovieResult:
        started_at = perf_counter()
        save_path: str | None = None
        success = False

        try:
            movie_root_path = self._get_movie_root_path()
            folder_name = self._build_movie_folder_name(request)
            save_path = posixpath.join(movie_root_path, folder_name)

            await self.openlist_client.ensure_path_ready(
                full_path=save_path,
                skip_prefix_path=movie_root_path,
            )
            await self.openlist_client.add_offline_download(path=save_path, magnet=request.magnet)

            success = True
            return MagnetIngestMovieResult(save_path=save_path)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Unexpected magnet ingest error movie=%r year=%s", request.original_title or request.title, request.year)
            raise AppException(status_code=500, message="创建离线下载任务失败") from exc
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Movie magnet ingest completed title=%r year=%s success=%s save_path=%r duration_ms=%.2f",
                request.original_title or request.title,
                request.year,
                success,
                save_path,
                duration_ms,
            )

    def _build_movie_folder_name(self, request: MagnetIngestMovieRequest) -> str:
        preferred_title = request.original_title or request.title or ""
        clean_title = self._sanitize_title(preferred_title)
        if not clean_title:
            raise AppException(status_code=400, message="电影标题不能为空")
        return f"{clean_title} ({request.year})"

    def _sanitize_title(self, title: str) -> str:
        cleaned_title = self.INVALID_PATH_CHAR_PATTERN.sub(" ", title.strip())
        cleaned_title = self.MULTIPLE_SPACE_PATTERN.sub(" ", cleaned_title).strip(" .")
        return cleaned_title

    def _get_movie_root_path(self) -> str:
        configured_path = (self.settings.alist_path_movie or "").strip()
        if not configured_path:
            raise AppException(status_code=503, message="OpenList 电影基础路径尚未配置")

        normalized_path = posixpath.normpath(configured_path)
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path.lstrip('/')}"
        return normalized_path
