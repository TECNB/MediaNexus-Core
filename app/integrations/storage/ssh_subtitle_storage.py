import errno
import logging
import posixpath
import stat
from pathlib import Path, PurePosixPath

import paramiko

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.integrations.storage.ssh_subtitle_storage")


class SSHSubtitleStorageError(Exception):
    """Base error for remote subtitle storage operations."""


class SSHSubtitleStorageConfigError(SSHSubtitleStorageError):
    """Raised when subtitle storage configuration is missing or invalid."""


class SSHSubtitleStorageConnectionError(SSHSubtitleStorageError):
    """Raised when the SSH/SFTP connection cannot be established."""


class SSHSubtitleStorageUploadError(SSHSubtitleStorageError):
    """Raised when a remote upload operation fails."""


class SSHSubtitleStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None

    def __enter__(self) -> "SSHSubtitleStorage":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._client is not None and self._sftp is not None:
            return

        self._validate_configuration()

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.settings.subtitle_ssh_host,
                port=self.settings.subtitle_ssh_port,
                username=self.settings.subtitle_ssh_username,
                password=self.settings.subtitle_ssh_password,
                timeout=self.settings.subtitle_ssh_timeout,
                banner_timeout=self.settings.subtitle_ssh_timeout,
                auth_timeout=self.settings.subtitle_ssh_timeout,
                key_filename=(
                    self.settings.subtitle_ssh_key_path if self.settings.subtitle_ssh_use_key else None
                ),
                look_for_keys=self.settings.subtitle_ssh_use_key,
                allow_agent=self.settings.subtitle_ssh_use_key,
            )
            self._client = client
            self._sftp = client.open_sftp()
        except (paramiko.SSHException, OSError) as exc:
            client.close()
            logger.warning(
                "Failed to connect to subtitle SSH storage host=%r port=%s username=%r error=%s",
                self.settings.subtitle_ssh_host,
                self.settings.subtitle_ssh_port,
                self.settings.subtitle_ssh_username,
                exc.__class__.__name__,
            )
            raise SSHSubtitleStorageConnectionError("failed to connect to subtitle storage") from exc

    def close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None

        if self._client is not None:
            self._client.close()
            self._client = None

    def upload_file(
        self,
        *,
        local_path: Path,
        remote_dir: str,
        remote_filename: str,
        overwrite: bool = False,
    ) -> str:
        sftp = self._get_sftp()
        normalized_remote_dir = posixpath.normpath(remote_dir)

        if not normalized_remote_dir.startswith("/"):
            raise SSHSubtitleStorageUploadError("remote directory must be an absolute POSIX path")

        try:
            self._ensure_remote_directory(normalized_remote_dir)
            final_filename = self._resolve_remote_filename(
                remote_dir=normalized_remote_dir,
                remote_filename=remote_filename,
                overwrite=overwrite,
            )
            remote_path = posixpath.join(normalized_remote_dir, final_filename)
            sftp.put(str(local_path), remote_path)
            return final_filename
        except SSHSubtitleStorageUploadError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            logger.warning(
                "Failed to upload subtitle file local=%r remote_dir=%r remote_filename=%r error=%s",
                str(local_path),
                normalized_remote_dir,
                remote_filename,
                exc.__class__.__name__,
            )
            raise SSHSubtitleStorageUploadError("failed to upload subtitle file") from exc

    def _validate_configuration(self) -> None:
        missing_fields: list[str] = []

        if not self.settings.subtitle_ssh_host:
            missing_fields.append("SUBTITLE_SSH_HOST")
        if not self.settings.subtitle_ssh_username:
            missing_fields.append("SUBTITLE_SSH_USERNAME")

        if not self.settings.subtitle_ssh_use_key and not self.settings.subtitle_ssh_password:
            missing_fields.append("SUBTITLE_SSH_PASSWORD")

        if missing_fields:
            raise SSHSubtitleStorageConfigError(
                f"missing subtitle ssh configuration: {', '.join(missing_fields)}"
            )

    def _get_sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            self.connect()

        if self._sftp is None:
            raise SSHSubtitleStorageConnectionError("subtitle storage connection is not available")

        return self._sftp

    def _ensure_remote_directory(self, remote_dir: str) -> None:
        sftp = self._get_sftp()
        parts = PurePosixPath(remote_dir).parts
        current_path = "/"

        for part in parts[1:]:
            current_path = posixpath.join(current_path, part)
            try:
                attrs = sftp.stat(current_path)
            except OSError as exc:
                if self._is_missing_path_error(exc):
                    sftp.mkdir(current_path)
                    continue
                raise SSHSubtitleStorageUploadError("failed to ensure remote directory") from exc

            if not stat.S_ISDIR(attrs.st_mode):
                raise SSHSubtitleStorageUploadError(
                    f"remote path exists but is not a directory: {current_path}"
                )

    def _resolve_remote_filename(self, *, remote_dir: str, remote_filename: str, overwrite: bool) -> str:
        candidate_name = PurePosixPath(remote_filename).name
        if not candidate_name:
            raise SSHSubtitleStorageUploadError("invalid remote filename")

        candidate_path = posixpath.join(remote_dir, candidate_name)
        if overwrite or not self._remote_path_exists(candidate_path):
            return candidate_name

        stem = Path(candidate_name).stem
        suffix = Path(candidate_name).suffix
        counter = 1

        while True:
            candidate_name = f"{stem} ({counter}){suffix}"
            candidate_path = posixpath.join(remote_dir, candidate_name)
            if not self._remote_path_exists(candidate_path):
                return candidate_name
            counter += 1

    def _remote_path_exists(self, remote_path: str) -> bool:
        try:
            self._get_sftp().stat(remote_path)
            return True
        except OSError as exc:
            if self._is_missing_path_error(exc):
                return False
            raise SSHSubtitleStorageUploadError("failed to inspect remote path") from exc

    def _is_missing_path_error(self, exc: OSError) -> bool:
        errno_value = getattr(exc, "errno", None)
        if errno_value == errno.ENOENT:
            return True
        return isinstance(exc, FileNotFoundError) or "No such file" in str(exc)
