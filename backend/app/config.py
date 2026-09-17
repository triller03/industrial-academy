from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI-Powered Industrial Academy"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"

    database_url: str = "sqlite:///./academy.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    device_limit_per_user: int = 3
    max_days_offline_sync: int = 90

    seed_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()