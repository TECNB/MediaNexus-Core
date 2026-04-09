from pydantic import BaseModel, ConfigDict, Field


class SubtitleUploadResult(BaseModel):
    target_path: str
    saved_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
