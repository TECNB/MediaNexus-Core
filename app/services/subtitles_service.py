import logging
import os
import posixpath
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Callable

from fastapi import UploadFile, status

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.integrations.storage.ssh_subtitle_storage import (
    SSHSubtitleStorage,
    SSHSubtitleStorageConfigError,
    SSHSubtitleStorageConnectionError,
    SSHSubtitleStorageUploadError,
)
from app.schemas.subtitles import SubtitleUploadResult

logger = logging.getLogger("app.services.subtitles")


class SubtitleUploadService:
    ALLOWED_SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub"}
    ALLOWED_ARCHIVE_EXTENSIONS = {".zip"}
    UNSUPPORTED_ARCHIVE_EXTENSIONS = {".rar"}
    ALLOWED_TARGET_ROOTS = (
        PurePosixPath("/srv/media/STRM/Movie"),
        PurePosixPath("/srv/media/STRM/TV"),
        PurePosixPath("/srv/media/STRM/Anime"),
    )

    def __init__(
        self,
        settings: Settings | None = None,
        storage_factory: Callable[[], SSHSubtitleStorage] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage_factory = storage_factory or (lambda: SSHSubtitleStorage(settings=self.settings))

    def upload_subtitles(
        self,
        *,
        file: UploadFile,
        target_path: str,
        overwrite: bool = False,
    ) -> SubtitleUploadResult:
        started_at = perf_counter()
        upload_name = self._get_safe_upload_filename(file.filename)
        normalized_target_path = self._validate_target_path(target_path)
        upload_extension = Path(upload_name).suffix.lower()
        success = False
        saved_files: list[str] = []
        skipped_files: list[str] = []

        try:
            self._validate_upload_extension(upload_extension)
            self._validate_upload_size(file)

            with tempfile.TemporaryDirectory(prefix="subtitle_upload_") as temp_dir:
                temp_path = Path(temp_dir) / upload_name
                self._copy_upload_to_temp(file=file, destination=temp_path)

                if upload_extension in self.ALLOWED_SUBTITLE_EXTENSIONS:
                    saved_files = self._upload_files(
                        local_files=[temp_path],
                        target_path=normalized_target_path,
                        overwrite=overwrite,
                    )
                else:
                    saved_files, skipped_files = self._handle_zip_upload(
                        archive_path=temp_path,
                        target_path=normalized_target_path,
                        overwrite=overwrite,
                    )

            success = True
            return SubtitleUploadResult(
                target_path=self._format_target_directory(normalized_target_path),
                saved_files=saved_files,
                skipped_files=skipped_files,
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Unexpected subtitle upload error for filename=%r", upload_name)
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="subtitle upload failed",
            ) from exc
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Subtitle upload completed filename=%r success=%s saved_files=%s skipped_files=%s duration_ms=%.2f",
                upload_name,
                success,
                len(saved_files),
                len(skipped_files),
                duration_ms,
            )

    def _validate_upload_extension(self, extension: str) -> None:
        if extension in self.UNSUPPORTED_ARCHIVE_EXTENSIONS:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="rar is not supported yet",
            )

        if extension in self.ALLOWED_SUBTITLE_EXTENSIONS or extension in self.ALLOWED_ARCHIVE_EXTENSIONS:
            return

        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="unsupported file type",
        )

    def _validate_upload_size(self, file: UploadFile) -> None:
        size_bytes = self._get_upload_size(file)
        max_size_bytes = self.settings.subtitle_max_upload_mb * 1024 * 1024

        if size_bytes > max_size_bytes:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"file size exceeds {self.settings.subtitle_max_upload_mb}MB limit",
            )

    def _get_upload_size(self, file: UploadFile) -> int:
        current_position = file.file.tell()
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(current_position)
        return size

    def _copy_upload_to_temp(self, *, file: UploadFile, destination: Path) -> None:
        file.file.seek(0)
        with destination.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)
        file.file.seek(0)

    def _handle_zip_upload(
        self,
        *,
        archive_path: Path,
        target_path: str,
        overwrite: bool,
    ) -> tuple[list[str], list[str]]:
        extract_dir = archive_path.parent / "extracted"
        self._extract_zip_archive(archive_path=archive_path, destination=extract_dir)

        subtitle_files: list[Path] = []
        skipped_files: list[str] = []

        for extracted_file in sorted(extract_dir.rglob("*")):
            if not extracted_file.is_file():
                continue

            if extracted_file.suffix.lower() in self.ALLOWED_SUBTITLE_EXTENSIONS:
                subtitle_files.append(extracted_file)
            else:
                skipped_files.append(extracted_file.name)

        if not subtitle_files:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="zip archive does not contain any subtitle files",
            )

        saved_files = self._upload_files(
            local_files=subtitle_files,
            target_path=target_path,
            overwrite=overwrite,
        )
        return saved_files, skipped_files

    def _extract_zip_archive(self, *, archive_path: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue

                    relative_path = self._normalize_zip_member_path(member.filename)
                    target_file = destination / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    with archive.open(member, "r") as source_file, target_file.open("wb") as output_file:
                        shutil.copyfileobj(source_file, output_file)
        except zipfile.BadZipFile as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="invalid zip file",
            ) from exc

    def _normalize_zip_member_path(self, member_name: str) -> Path:
        normalized_member = member_name.replace("\\", "/").strip()
        if not normalized_member:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="zip archive contains invalid file paths",
            )

        posix_member = PurePosixPath(normalized_member)
        if posix_member.is_absolute() or any(part == ".." for part in posix_member.parts):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="zip archive contains invalid file paths",
            )

        return Path(*posix_member.parts)

    def _upload_files(self, *, local_files: list[Path], target_path: str, overwrite: bool) -> list[str]:
        remote_directory = posixpath.normpath(target_path)

        try:
            with self.storage_factory() as storage:
                saved_files: list[str] = []
                for local_file in local_files:
                    saved_name = storage.upload_file(
                        local_path=local_file,
                        remote_dir=remote_directory,
                        remote_filename=self._get_safe_upload_filename(local_file.name),
                        overwrite=overwrite,
                    )
                    saved_files.append(saved_name)
                return saved_files
        except SSHSubtitleStorageConfigError as exc:
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="subtitle upload is not configured",
            ) from exc
        except SSHSubtitleStorageConnectionError as exc:
            raise AppException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="failed to connect to remote subtitle server",
            ) from exc
        except SSHSubtitleStorageUploadError as exc:
            raise AppException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="failed to upload subtitle to remote server",
            ) from exc

    def _validate_target_path(self, target_path: str) -> str:
        cleaned_path = target_path.strip().replace("\\", "/")
        if not cleaned_path or "\x00" in cleaned_path:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="invalid target path",
            )

        candidate_path = PurePosixPath(cleaned_path)
        if not candidate_path.is_absolute() or any(part == ".." for part in candidate_path.parts):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="invalid target path",
            )

        normalized_path = PurePosixPath(posixpath.normpath(cleaned_path))
        if not self._is_allowed_target_path(normalized_path):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="invalid target path",
            )

        return str(normalized_path)

    def _is_allowed_target_path(self, target_path: PurePosixPath) -> bool:
        return any(
            target_path == allowed_root or allowed_root in target_path.parents
            for allowed_root in self.ALLOWED_TARGET_ROOTS
        )

    def _get_safe_upload_filename(self, filename: str | None) -> str:
        normalized_name = PurePosixPath((filename or "").replace("\\", "/")).name.strip()
        if not normalized_name or normalized_name in {".", ".."}:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="invalid file name",
            )
        return normalized_name

    def _format_target_directory(self, target_path: str) -> str:
        return f"{target_path.rstrip('/')}/"
