import unittest

from app.core.config import Settings
from app.integrations.emby.client import EmbyClient, EmbyItemMatch


class TestableEmbyClient(EmbyClient):
    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings=settings)
        self.item_matches: dict[str, EmbyItemMatch] = {}
        self.refreshed_item_ids: list[str] = []
        self.reported_paths: list[str] = []

    def find_item_by_path(self, media_path: str) -> EmbyItemMatch | None:
        return self.item_matches.get(media_path)

    def refresh_item(self, item_id: str) -> None:
        self.refreshed_item_ids.append(item_id)

    def report_media_updated(self, media_paths: list[str]) -> None:
        self.reported_paths.extend(media_paths)


class EmbyClientTests(unittest.TestCase):
    def test_refresh_media_paths_maps_prefix_and_refreshes_exact_items(self) -> None:
        settings = Settings(
            emby_url="http://127.0.0.1:8096",
            emby_api_key="test-key",
            emby_path_prefix_from="/strm",
            emby_path_prefix_to="/srv/media/STRM",
        )
        client = TestableEmbyClient(settings=settings)
        mapped_path = "/srv/media/STRM/Movie/Test Movie (2024)/Test Movie.strm"
        client.item_matches[mapped_path] = EmbyItemMatch(item_id="movie-1", path=mapped_path)

        client.refresh_media_paths(
            [
                "/strm/Movie/Test Movie (2024)/Test Movie.strm",
                "/strm/Movie/Test Movie (2024)/Test Movie.strm",
            ]
        )

        self.assertEqual(client.refreshed_item_ids, ["movie-1"])
        self.assertEqual(client.reported_paths, [])

    def test_refresh_media_paths_falls_back_to_media_updated_for_unresolved_items(self) -> None:
        settings = Settings(
            emby_url="http://127.0.0.1:8096/emby",
            emby_api_key="test-key",
        )
        client = TestableEmbyClient(settings=settings)
        resolved_path = "/srv/media/STRM/TV/Test Show/S01E01.strm"
        unresolved_path = "/srv/media/STRM/TV/Test Show/S01E02.strm"
        client.item_matches[resolved_path] = EmbyItemMatch(item_id="episode-1", path=resolved_path)

        client.refresh_media_paths([resolved_path, unresolved_path])

        self.assertEqual(client.refreshed_item_ids, ["episode-1"])
        self.assertEqual(client.reported_paths, [unresolved_path])
        self.assertEqual(client.base_url, "http://127.0.0.1:8096/emby")


if __name__ == "__main__":
    unittest.main()
