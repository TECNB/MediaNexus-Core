from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class MagnetIngestMovieRequest(BaseModel):
    magnet: str
    title: str | None = None
    original_title: str | None = None
    year: int

    model_config = ConfigDict(extra="forbid")

    @field_validator("magnet")
    @classmethod
    def validate_magnet(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value or not normalized_value.startswith("magnet:?"):
            raise ValueError("magnet must start with 'magnet:?'")
        return normalized_value

    @field_validator("title", "original_title", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("year", mode="before")
    @classmethod
    def parse_year(cls, value: int | str) -> int:
        if isinstance(value, str):
            normalized_value = value.strip()
            if not normalized_value:
                raise ValueError("year is required")
            return int(normalized_value)
        return int(value)

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int) -> int:
        max_year = datetime.now().year + 2
        if value < 1888 or value > max_year:
            raise ValueError("year is invalid")
        return value

    @model_validator(mode="after")
    def validate_title_fields(self) -> "MagnetIngestMovieRequest":
        if not self.original_title and not self.title:
            raise ValueError("either original_title or title is required")
        return self


class MagnetIngestMovieResult(BaseModel):
    save_path: str

    model_config = ConfigDict(extra="forbid")


class SeriesMagnetIngestRequest(BaseModel):
    magnet: str
    title: str | None = None
    original_title: str | None = None
    season_number: int

    model_config = ConfigDict(extra="forbid")

    @field_validator("magnet")
    @classmethod
    def validate_magnet(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value or not normalized_value.startswith("magnet:?"):
            raise ValueError("magnet must start with 'magnet:?'")
        return normalized_value

    @field_validator("title", "original_title", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("season_number", mode="before")
    @classmethod
    def parse_season_number(cls, value: int | str) -> int:
        if isinstance(value, str):
            normalized_value = value.strip()
            if not normalized_value:
                raise ValueError("season_number is required")
            return int(normalized_value)
        return int(value)

    @field_validator("season_number")
    @classmethod
    def validate_season_number(cls, value: int) -> int:
        if value < 1:
            raise ValueError("season_number must be greater than or equal to 1")
        return value

    @model_validator(mode="after")
    def validate_title_fields(self) -> "SeriesMagnetIngestRequest":
        if not self.original_title and not self.title:
            raise ValueError("either original_title or title is required")
        return self


class SeriesMagnetIngestResult(BaseModel):
    save_path: str
    series_name: str
    season_folder: str

    model_config = ConfigDict(extra="forbid")
