import logging
import posixpath
import re
from time import perf_counter

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.integrations.openlist.client import OpenListClient
from app.schemas.magnet_ingest import (
    MagnetIngestMovieRequest,
    MagnetIngestMovieResult,
    SeriesMagnetIngestRequest,
    SeriesMagnetIngestResult,
)

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
                missing_prefix_message="OpenList 电影基础路径不存在",
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

    async def ingest_series(self, request: SeriesMagnetIngestRequest) -> SeriesMagnetIngestResult:
        started_at = perf_counter()
        save_path: str | None = None
        series_name: str | None = None
        season_folder: str | None = None
        success = False

        try:
            tv_root_path = self._get_tv_root_path()
            series_name = self._build_series_name(request)
            season_folder = self._build_season_folder(request.season_number)
            save_path = self._build_save_path(tv_root_path, series_name, season_folder)

            logger.info(
                "Preparing series magnet ingest series_name=%r season_folder=%r save_path=%r",
                series_name,
                season_folder,
                save_path,
            )

            logger.info("Ensuring OpenList path ready save_path=%r", save_path)
            await self.openlist_client.ensure_path_ready(
                full_path=save_path,
                skip_prefix_path=tv_root_path,
                missing_prefix_message="OpenList 剧集基础路径不存在",
            )
            logger.info("Submitting OpenList offline download save_path=%r", save_path)
            await self.openlist_client.add_offline_download(path=save_path, magnet=request.magnet)

            success = True
            return SeriesMagnetIngestResult(
                save_path=save_path,
                series_name=series_name,
                season_folder=season_folder,
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected series magnet ingest error title=%r season_number=%s",
                request.original_title or request.title,
                request.season_number,
            )
            raise AppException(status_code=500, message="创建剧集离线下载任务失败") from exc
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Series magnet ingest completed series_name=%r season_folder=%r success=%s save_path=%r duration_ms=%.2f",
                series_name,
                season_folder,
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

    def _build_series_name(self, request: SeriesMagnetIngestRequest) -> str:
        preferred_title = request.original_title or request.title or ""
        clean_title = self._sanitize_title(preferred_title)
        if not clean_title:
            raise AppException(status_code=400, message="剧集标题不能为空")
        return clean_title

    def _build_season_folder(self, season_number: int) -> str:
        return f"Season {season_number:02d}"

    def _build_save_path(self, root_path: str, *segments: str) -> str:
        return posixpath.join(root_path, *segments)

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

    def _get_tv_root_path(self) -> str:
        configured_path = (self.settings.alist_path_tv or "").strip()
        if not configured_path:
            raise AppException(status_code=503, message="OpenList 剧集基础路径尚未配置")

        normalized_path = posixpath.normpath(configured_path)
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path.lstrip('/')}"
        return normalized_path
