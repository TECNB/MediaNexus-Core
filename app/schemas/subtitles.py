from typing import Annotated, Any

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubtitleUploadRequest(BaseModel):
    target_path: str | None = Field(default=None)
    media_type: str | None = Field(default=None)
    tmdb_id: int | None = Field(default=None, gt=0)
    imdb_id: str | None = Field(default=None)
    library_title: str | None = Field(default=None)
    library_year: str | None = Field(default=None)
    overwrite: bool = True

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "target_path": "/srv/media/STRM/Movie/Interstellar (2014)",
                    "overwrite": True,
                },
                {
                    "media_type": "movie",
                    "tmdb_id": 157336,
                    "imdb_id": "tt0816692",
                    "overwrite": True,
                },
            ]
        },
    )

    @field_validator(
        "target_path",
        "media_type",
        "imdb_id",
        "library_title",
        "library_year",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("tmdb_id", mode="before")
    @classmethod
    def normalize_tmdb_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @classmethod
    def as_form(
        cls,
        target_path: Annotated[
            str | None,
            Form(description="Remote STRM target directory for manual target_path mode"),
        ] = None,
        media_type: Annotated[
            str | None,
            Form(description="Associated media type. Association mode currently supports movie only"),
        ] = None,
        tmdb_id: Annotated[
            int | None,
            Form(description="Stable TMDb movie ID used first when resolving the movie directory"),
        ] = None,
        imdb_id: Annotated[
            str | None,
            Form(description="Stable IMDb movie ID used as fallback when tmdb_id is unavailable"),
        ] = None,
        library_title: Annotated[
            str | None,
            Form(
                description="Legacy associated library title kept for backward compatibility and ignored by the new movie ID resolution flow"
            ),
        ] = None,
        library_year: Annotated[
            str | None,
            Form(
                description="Legacy associated library year kept for backward compatibility and ignored by the new movie ID resolution flow"
            ),
        ] = None,
        overwrite: Annotated[bool, Form(description="Whether to overwrite existing files")] = True,
    ) -> "SubtitleUploadRequest":
        return cls(
            target_path=target_path,
            media_type=media_type,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            library_title=library_title,
            library_year=library_year,
            overwrite=overwrite,
        )


class SubtitleUploadResult(BaseModel):
    target_path: str
    saved_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
