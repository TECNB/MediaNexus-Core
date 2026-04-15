from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class SonarrSeriesImage(BaseModel):
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


class SonarrSeriesSeason(BaseModel):
    season_number: int | None = Field(default=None, alias="seasonNumber")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("season_number", mode="before")
    @classmethod
    def normalize_season_number(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class SonarrSeriesLookupItem(BaseModel):
    title: str | None = None
    original_title: str | None = Field(default=None, alias="originalTitle")
    year: int | None = None
    overview: str | None = None
    images: list[SonarrSeriesImage] = Field(default_factory=list)
    seasons: list["SonarrSeriesSeason"] = Field(default_factory=list)
    tvdb_id: int | None = Field(default=None, alias="tvdbId")
    imdb_id: str | None = Field(default=None, alias="imdbId")
    tmdb_id: int | None = Field(default=None, alias="tmdbId")
    status: str | None = None
    network: str | None = None
    series_type: str | None = Field(default=None, alias="seriesType")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator(
        "title",
        "original_title",
        "overview",
        "imdb_id",
        "status",
        "network",
        "series_type",
        mode="before",
    )
    @classmethod
    def normalize_string_fields(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("tvdb_id", "tmdb_id", "year", mode="before")
    @classmethod
    def normalize_int_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("images", mode="before")
    @classmethod
    def normalize_images(cls, value: Any) -> list[dict[str, Any]] | list[SonarrSeriesImage]:
        if value is None:
            return []
        return value

    @field_validator("seasons", mode="before")
    @classmethod
    def normalize_seasons(cls, value: Any) -> list[dict[str, Any]] | list["SonarrSeriesSeason"]:
        if value is None:
            return []
        return value


class SonarrSeriesLookupResponse(RootModel[list[SonarrSeriesLookupItem]]):
    pass
