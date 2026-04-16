import logging
from time import perf_counter

from app.core.exceptions import (
    AppException,
    InvalidUpstreamResponseError,
    UpstreamServiceError,
    UpstreamServiceUnavailable,
)
from app.integrations.radarr.client import RadarrClient
from app.integrations.radarr.schemas import RadarrQualityProfile
from app.schemas.resources import MovieQualityProfileItem, MovieQualityProfilesResult

logger = logging.getLogger("app.services.movie_quality_profiles")


class MovieQualityProfileService:
    def __init__(self, radarr_client: RadarrClient | None = None) -> None:
        self.radarr_client = radarr_client or RadarrClient()

    async def get_quality_profiles(self) -> MovieQualityProfilesResult:
        started_at = perf_counter()
        success = False
        result_count = 0
        error_type = "none"

        try:
            profiles = await self.radarr_client.get_quality_profiles()
            items = self._map_profiles(profiles)
            result_count = len(items)
            success = True
            return MovieQualityProfilesResult(items=items)
        except (
            UpstreamServiceUnavailable,
            UpstreamServiceError,
            InvalidUpstreamResponseError,
        ) as exc:
            error_type = exc.__class__.__name__
            logger.warning("Radarr quality profile load failed error_type=%s", error_type)
            raise UpstreamServiceError(message="failed to load quality profiles") from exc
        except AppException as exc:
            error_type = exc.__class__.__name__
            raise
        except Exception as exc:
            error_type = exc.__class__.__name__
            logger.exception("Unexpected quality profile load error")
            raise
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "Movie quality profiles completed success=%s results=%s duration_ms=%.2f error_type=%s",
                success,
                result_count,
                duration_ms,
                error_type,
            )

    def _map_profiles(
        self,
        profiles: list[RadarrQualityProfile],
    ) -> list[MovieQualityProfileItem]:
        valid_profiles = [
            profile
            for profile in profiles
            if profile.id is not None and profile.name and profile.name.strip()
        ]
        default_profile_id = valid_profiles[0].id if valid_profiles else None

        return [
            MovieQualityProfileItem(
                id=profile.id,
                name=(profile.name or "").strip(),
                is_default=profile.id == default_profile_id,
            )
            for profile in valid_profiles
            if profile.id is not None
        ]
