from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator


class RadarrMovieImage(BaseModel):
    cover_type: str | None = Field(default=None, alias="coverType")
    url: str | None = None
    remote_url: str | None = Field(default=None, alias="remoteUrl")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("cover_type", "url", "remote_url", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class RadarrMovieLookupItem(BaseModel):
    title: str | None = None
    original_title: str | None = Field(default=None, alias="originalTitle")
    year: int | None = None
    overview: str | None = None
    images: list[RadarrMovieImage] = Field(default_factory=list)
    tmdb_id: int | None = Field(default=None, alias="tmdbId")
    imdb_id: str | None = Field(default=None, alias="imdbId")
    status: str | None = None
    minimum_availability: str | None = Field(default=None, alias="minimumAvailability")
    is_available: bool | None = Field(default=None, alias="isAvailable")
    in_cinemas: str | None = Field(default=None, alias="inCinemas")
    digital_release: str | None = Field(default=None, alias="digitalRelease")
    physical_release: str | None = Field(default=None, alias="physicalRelease")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator(
        "title",
        "original_title",
        "overview",
        "imdb_id",
        "status",
        "minimum_availability",
        "in_cinemas",
        "digital_release",
        "physical_release",
        mode="before",
    )
    @classmethod
    def normalize_string_fields(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("tmdb_id", "year", mode="before")
    @classmethod
    def normalize_int_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("images", mode="before")
    @classmethod
    def normalize_images(cls, value: Any) -> list[dict[str, Any]] | list[RadarrMovieImage]:
        if value is None:
            return []
        return value


class RadarrMovieLookupResponse(RootModel[list[RadarrMovieLookupItem]]):
    pass


class RadarrMovieResource(BaseModel):
    id: int | None = None
    title: str | None = None
    year: int | None = None
    tmdb_id: int | None = Field(default=None, alias="tmdbId")
    imdb_id: str | None = Field(default=None, alias="imdbId")
    path: str | None = None
    title_slug: str | None = Field(default=None, alias="titleSlug")
    root_folder_path: str | None = Field(default=None, alias="rootFolderPath")
    quality_profile_id: int | None = Field(default=None, alias="qualityProfileId")
    minimum_availability: str | None = Field(default=None, alias="minimumAvailability")
    raw_payload: dict[str, Any] = Field(default_factory=dict, exclude=True)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def preserve_raw_payload(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {**value, "raw_payload": dict(value)}
        return value

    @field_validator(
        "title",
        "imdb_id",
        "path",
        "title_slug",
        "root_folder_path",
        "minimum_availability",
        mode="before",
    )
    @classmethod
    def normalize_string_fields(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("id", "tmdb_id", "year", "quality_profile_id", mode="before")
    @classmethod
    def normalize_int_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class RadarrMovieResourceResponse(RootModel[list[RadarrMovieResource]]):
    pass


class RadarrRootFolder(BaseModel):
    path: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class RadarrRootFolderResponse(RootModel[list[RadarrRootFolder]]):
    pass


class RadarrQualityProfile(BaseModel):
    id: int | None = None
    name: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class RadarrQualityProfileResponse(RootModel[list[RadarrQualityProfile]]):
    pass
