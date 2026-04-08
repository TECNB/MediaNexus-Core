from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


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
