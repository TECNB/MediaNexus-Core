import tempfile
import unittest
from pathlib import Path

from app.integrations.storage.ssh_subtitle_storage import SSHSubtitleStorageFileInfo
from app.services.subtitles_service import SubtitleUploadService


class FakeSubtitleStorage:
    def __init__(self, remote_files: list[SSHSubtitleStorageFileInfo]) -> None:
        self.remote_files = remote_files
        self.upload_calls: list[dict[str, object]] = []

    def __enter__(self) -> "FakeSubtitleStorage":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def list_files(self, remote_dir: str) -> list[SSHSubtitleStorageFileInfo]:
        return self.remote_files

    def upload_file(
        self,
        *,
        local_path: Path,
        remote_dir: str,
        remote_filename: str,
        overwrite: bool = False,
    ) -> str:
        self.upload_calls.append(
            {
                "local_path": local_path,
                "remote_dir": remote_dir,
                "remote_filename": remote_filename,
                "overwrite": overwrite,
            }
        )
        return remote_filename


class SubtitleUploadServiceTests(unittest.TestCase):
    def _create_subtitle_file(self, suffix: str = ".srt") -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        subtitle_path = Path(temp_dir.name) / f"subtitle{suffix}"
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
        return temp_dir, subtitle_path

    def test_upload_files_copies_same_subtitle_for_each_strm(self) -> None:
        storage = FakeSubtitleStorage(
            [
                SSHSubtitleStorageFileInfo(name="Episode 02.strm", size=100, is_dir=False),
                SSHSubtitleStorageFileInfo(name="Episode 01.strm", size=50, is_dir=False),
                SSHSubtitleStorageFileInfo(name="notes.txt", size=10, is_dir=False),
            ]
        )
        service = SubtitleUploadService(storage_factory=lambda: storage)
        temp_dir, subtitle_path = self._create_subtitle_file()

        try:
            saved_files = service._upload_files(
                local_files=[subtitle_path],
                target_path="/srv/media/STRM/TV/Test Show",
                overwrite=True,
            )
        finally:
            temp_dir.cleanup()

        self.assertEqual(saved_files, ["Episode 01.srt", "Episode 02.srt"])
        self.assertEqual(
            [call["remote_filename"] for call in storage.upload_calls],
            ["Episode 01.srt", "Episode 02.srt"],
        )

    def test_upload_files_falls_back_to_largest_video_when_no_strm_exists(self) -> None:
        storage = FakeSubtitleStorage(
            [
                SSHSubtitleStorageFileInfo(name="Movie Trailer.mp4", size=100, is_dir=False),
                SSHSubtitleStorageFileInfo(name="Movie Feature.mkv", size=500, is_dir=False),
                SSHSubtitleStorageFileInfo(name="Movie Sample.mkv", size=200, is_dir=False),
            ]
        )
        service = SubtitleUploadService(storage_factory=lambda: storage)
        temp_dir, subtitle_path = self._create_subtitle_file(".ass")

        try:
            saved_files = service._upload_files(
                local_files=[subtitle_path],
                target_path="/srv/media/STRM/Movie/Test Movie (2024)",
                overwrite=False,
            )
        finally:
            temp_dir.cleanup()

        self.assertEqual(saved_files, ["Movie Feature.ass"])
        self.assertEqual(
            [call["remote_filename"] for call in storage.upload_calls],
            ["Movie Feature.ass"],
        )


if __name__ == "__main__":
    unittest.main()
