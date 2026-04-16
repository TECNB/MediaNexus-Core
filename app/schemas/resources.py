from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MovieSearchItem(BaseModel):
    id: str
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str = ""
    poster: str | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    status: Literal["announced", "released", "unknown"] = "unknown"

    model_config = ConfigDict(extra="forbid")


class MovieSearchResult(BaseModel):
    items: list[MovieSearchItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MovieQualityProfileItem(BaseModel):
    id: int
    name: str
    is_default: bool = False

    model_config = ConfigDict(extra="forbid")


class MovieQualityProfilesResult(BaseModel):
    items: list[MovieQualityProfileItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MovieAddRequest(BaseModel):
    tmdb_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    year: int = Field(gt=0)
    quality_profile_id: int = Field(alias="qualityProfileId", gt=0)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class MovieAddResponseMovie(BaseModel):
    id: int
    tmdb_id: int
    title: str
    year: int
    quality_profile_id: int = Field(alias="qualityProfileId")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class MovieAddResult(BaseModel):
    status: Literal["search_started"] = "search_started"
    action: Literal["added_then_searched", "updated_existing_then_searched"]
    movie: MovieAddResponseMovie

    model_config = ConfigDict(extra="forbid")


class SeriesSearchItem(BaseModel):
    id: str
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str = ""
    poster: str | None = None
    tvdb_id: int | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    status: str = "unknown"
    network: str | None = None
    series_type: str | None = None

    model_config = ConfigDict(extra="forbid")


class SeriesSearchResult(BaseModel):
    items: list[SeriesSearchItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SeriesSeasonsResponseData(BaseModel):
    tvdb_id: int
    title: str
    season_count: int
    season_numbers: list[int] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
