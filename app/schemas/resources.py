from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
