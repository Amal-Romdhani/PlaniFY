from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Charge la configuration de l'application."""

    database_url: str
    anthropic_api_key: str = ""
    anthropic_model: str
    jwt_secret: str
    jwt_expire_minutes: int
    monitoring_interval_minutes: int
    cors_origins: str = "http://localhost:5173,http://localhost"

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
