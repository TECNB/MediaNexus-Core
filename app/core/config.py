import json
from functools import lru_cache
from typing import Any

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MediaNexus API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./app.db"
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    radarr_scheme: str = "http"
    radarr_host: str | None = None
    radarr_port: int | None = None
    radarr_api_key: str | None = None
    radarr_timeout: float = 10.0
    sonarr_scheme: str = "http"
    sonarr_host: str | None = None
    sonarr_port: int | None = None
    sonarr_api_key: str | None = None
    sonarr_timeout: float = 10.0
    subtitle_ssh_host: str | None = None
    subtitle_ssh_port: int = 22
    subtitle_ssh_username: str | None = None
    subtitle_ssh_password: str | None = None
    subtitle_ssh_timeout: float = 10.0
    subtitle_max_upload_mb: int = 100
    subtitle_ssh_key_path: str | None = None
    subtitle_ssh_use_key: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator(
        "radarr_host",
        "radarr_port",
        "radarr_api_key",
        "sonarr_host",
        "sonarr_port",
        "sonarr_api_key",
        "subtitle_ssh_host",
        "subtitle_ssh_username",
        "subtitle_ssh_password",
        "subtitle_ssh_key_path",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("radarr_scheme", "sonarr_scheme", mode="before")
    @classmethod
    def parse_service_scheme(cls, value: Any) -> str:
        if value is None:
            return "http"
        if isinstance(value, str):
            cleaned = value.strip().lower()
            return cleaned or "http"
        return str(value).strip().lower()

    @field_validator("radarr_scheme", "sonarr_scheme")
    @classmethod
    def validate_service_scheme(cls, value: str, info: ValidationInfo) -> str:
        if value not in {"http", "https"}:
            raise ValueError(f"{info.field_name.upper()} must be either 'http' or 'https'")
        return value

    @field_validator("radarr_timeout", "sonarr_timeout", "subtitle_ssh_timeout", mode="before")
    @classmethod
    def parse_service_timeout(cls, value: Any) -> float:
        if value is None:
            return 10.0
        if isinstance(value, str) and value.strip() == "":
            return 10.0
        return float(value)

    @field_validator("radarr_timeout", "sonarr_timeout", "subtitle_ssh_timeout")
    @classmethod
    def validate_service_timeout(cls, value: float, info: ValidationInfo) -> float:
        if value <= 0:
            raise ValueError(f"{info.field_name.upper()} must be greater than 0")
        return value

    @field_validator("subtitle_ssh_port", "subtitle_max_upload_mb", mode="before")
    @classmethod
    def parse_positive_int_setting(cls, value: Any, info: ValidationInfo) -> int:
        default_values = {
            "subtitle_ssh_port": 22,
            "subtitle_max_upload_mb": 100,
        }
        if value is None:
            return default_values[info.field_name]
        if isinstance(value, str) and value.strip() == "":
            return default_values[info.field_name]
        return int(value)

    @field_validator("subtitle_ssh_port", "subtitle_max_upload_mb")
    @classmethod
    def validate_positive_int_setting(cls, value: int, info: ValidationInfo) -> int:
        if value <= 0:
            raise ValueError(f"{info.field_name.upper()} must be greater than 0")
        return value

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []

        if isinstance(value, str):
            raw_value = value.strip()
            if raw_value.startswith("["):
                parsed = json.loads(raw_value)
                if not isinstance(parsed, list):
                    raise ValueError("BACKEND_CORS_ORIGINS must be a list")
                return [str(item).rstrip("/") for item in parsed]

            return [item.strip().rstrip("/") for item in raw_value.split(",") if item.strip()]

        if isinstance(value, list):
            return [str(item).rstrip("/") for item in value]

        raise ValueError("Invalid BACKEND_CORS_ORIGINS value")


@lru_cache
def get_settings() -> Settings:
    return Settings()
