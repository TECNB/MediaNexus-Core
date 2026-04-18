import tempfile
import unittest
from pathlib import Path

from app.core.exceptions import AppException
from app.integrations.radarr.schemas import RadarrMovieLookupItem, RadarrMovieResource
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


class FakeEmbyClient:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.refreshed_media_paths: list[str] = []

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    def refresh_media_paths(self, media_paths: list[str]) -> None:
        self.refreshed_media_paths.extend(media_paths)


class FakeRadarrClient:
    def __init__(
        self,
        *,
        movie_by_tmdb: RadarrMovieResource | None = None,
        movie_by_imdb: RadarrMovieResource | None = None,
        lookup_by_tmdb: RadarrMovieLookupItem | None = None,
        lookup_by_imdb: RadarrMovieLookupItem | None = None,
    ) -> None:
        self.movie_by_tmdb = movie_by_tmdb
        self.movie_by_imdb = movie_by_imdb
        self.lookup_by_tmdb = lookup_by_tmdb
        self.lookup_by_imdb = lookup_by_imdb
        self.calls: list[tuple[str, object]] = []

    async def get_movie_by_tmdb_id(self, tmdb_id: int) -> RadarrMovieResource | None:
        self.calls.append(("get_movie_by_tmdb_id", tmdb_id))
        return self.movie_by_tmdb

    async def get_movie_by_imdb_id(self, imdb_id: str) -> RadarrMovieResource | None:
        self.calls.append(("get_movie_by_imdb_id", imdb_id))
        return self.movie_by_imdb

    async def lookup_movie_by_tmdb_id(self, tmdb_id: int) -> RadarrMovieLookupItem | None:
        self.calls.append(("lookup_movie_by_tmdb_id", tmdb_id))
        return self.lookup_by_tmdb

    async def lookup_movie_by_imdb_id(self, imdb_id: str) -> RadarrMovieLookupItem | None:
        self.calls.append(("lookup_movie_by_imdb_id", imdb_id))
        return self.lookup_by_imdb


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
        emby_client = FakeEmbyClient()
        service = SubtitleUploadService(
            storage_factory=lambda: storage,
            emby_client_factory=lambda: emby_client,
        )
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
        self.assertEqual(
            emby_client.refreshed_media_paths,
            [
                "/srv/media/STRM/TV/Test Show/Episode 01.strm",
                "/srv/media/STRM/TV/Test Show/Episode 02.strm",
            ],
        )

    def test_upload_files_falls_back_to_largest_video_when_no_strm_exists(self) -> None:
        storage = FakeSubtitleStorage(
            [
                SSHSubtitleStorageFileInfo(name="Movie Trailer.mp4", size=100, is_dir=False),
                SSHSubtitleStorageFileInfo(name="Movie Feature.mkv", size=500, is_dir=False),
                SSHSubtitleStorageFileInfo(name="Movie Sample.mkv", size=200, is_dir=False),
            ]
        )
        emby_client = FakeEmbyClient()
        service = SubtitleUploadService(
            storage_factory=lambda: storage,
            emby_client_factory=lambda: emby_client,
        )
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
        self.assertEqual(
            emby_client.refreshed_media_paths,
            ["/srv/media/STRM/Movie/Test Movie (2024)/Movie Feature.mkv"],
        )

    def test_resolve_target_path_prefers_radarr_movie_path_for_tmdb_id(self) -> None:
        radarr_client = FakeRadarrClient(
            movie_by_tmdb=RadarrMovieResource.model_validate(
                {
                    "tmdbId": 157336,
                    "imdbId": "tt0816692",
                    "title": "Interstellar",
                    "year": 2014,
                    "path": "/srv/media/STRM/Movie/Interstellar (2014)",
                }
            )
        )
        service = SubtitleUploadService(radarr_client=radarr_client)

        resolved_path = service.resolve_target_path(
            target_path=None,
            media_type="movie",
            tmdb_id=157336,
            imdb_id=None,
            library_title=None,
            library_year=None,
        )

        self.assertEqual(resolved_path, "/srv/media/STRM/Movie/Interstellar (2014)")
        self.assertEqual(radarr_client.calls, [("get_movie_by_tmdb_id", 157336)])

    def test_resolve_target_path_falls_back_to_radarr_title_and_year_when_path_missing(self) -> None:
        radarr_client = FakeRadarrClient(
            movie_by_tmdb=RadarrMovieResource.model_validate(
                {
                    "tmdbId": 872585,
                    "title": "Oppenheimer",
                    "year": 2023,
                }
            )
        )
        service = SubtitleUploadService(radarr_client=radarr_client)

        resolved_path = service.resolve_target_path(
            target_path=None,
            media_type="movie",
            tmdb_id=872585,
            imdb_id=None,
            library_title="奥本海默",
            library_year="2023",
        )

        self.assertEqual(resolved_path, "/srv/media/STRM/Movie/Oppenheimer (2023)")

    def test_resolve_target_path_uses_imdb_id_when_tmdb_id_is_missing(self) -> None:
        radarr_client = FakeRadarrClient(
            movie_by_imdb=RadarrMovieResource.model_validate(
                {
                    "imdbId": "tt0816692",
                    "title": "Interstellar",
                    "year": 2014,
                    "path": "/srv/media/STRM/Movie/Interstellar (2014)",
                }
            )
        )
        service = SubtitleUploadService(radarr_client=radarr_client)

        resolved_path = service.resolve_target_path(
            target_path=None,
            media_type="movie",
            tmdb_id=None,
            imdb_id="tt0816692",
            library_title=None,
            library_year=None,
        )

        self.assertEqual(resolved_path, "/srv/media/STRM/Movie/Interstellar (2014)")
        self.assertEqual(radarr_client.calls, [("get_movie_by_imdb_id", "tt0816692")])

    def test_resolve_target_path_requires_stable_media_id_for_movie_association(self) -> None:
        service = SubtitleUploadService(radarr_client=FakeRadarrClient())

        with self.assertRaises(AppException) as exc_info:
            service.resolve_target_path(
                target_path=None,
                media_type="movie",
                tmdb_id=None,
                imdb_id=None,
                library_title="Interstellar",
                library_year="2014",
            )

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(exc_info.exception.message, "missing stable media id")

    def test_resolve_target_path_raises_not_found_when_radarr_has_no_movie(self) -> None:
        service = SubtitleUploadService(radarr_client=FakeRadarrClient())

        with self.assertRaises(AppException) as exc_info:
            service.resolve_target_path(
                target_path=None,
                media_type="movie",
                tmdb_id=999999,
                imdb_id=None,
                library_title=None,
                library_year=None,
            )

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.message, "movie not found in Radarr")

    def test_resolve_target_path_rejects_radarr_path_outside_allowed_roots(self) -> None:
        radarr_client = FakeRadarrClient(
            movie_by_tmdb=RadarrMovieResource.model_validate(
                {
                    "tmdbId": 157336,
                    "title": "Interstellar",
                    "year": 2014,
                    "path": "/data/movies/Interstellar (2014)",
                }
            )
        )
        service = SubtitleUploadService(radarr_client=radarr_client)

        with self.assertRaises(AppException) as exc_info:
            service.resolve_target_path(
                target_path=None,
                media_type="movie",
                tmdb_id=157336,
                imdb_id=None,
                library_title=None,
                library_year=None,
            )

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(
            exc_info.exception.message,
            "radarr movie path is not within allowed target roots",
        )

    def test_resolve_target_path_keeps_manual_target_path_mode_working(self) -> None:
        service = SubtitleUploadService(radarr_client=FakeRadarrClient())

        resolved_path = service.resolve_target_path(
            target_path="/srv/media/STRM/Movie/Interstellar (2014)/",
            media_type=None,
            tmdb_id=None,
            imdb_id=None,
            library_title=None,
            library_year=None,
        )

        self.assertEqual(resolved_path, "/srv/media/STRM/Movie/Interstellar (2014)")


if __name__ == "__main__":
    unittest.main()
