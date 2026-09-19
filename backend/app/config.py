from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI-Powered Industrial Academy"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"

    # Production asks "no". Set ENVIRONMENT=production when deploying (enables
    # the startup guard, HTTPS enforcement and restricted CORS defaults).
    environment: str = "development"
    database_url: str = "sqlite:///./academy.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    # Network hardening
    cors_origins: str = "*"  # comma-separated; "*" = allow all (development)
    require_https: bool = False
    trusted_proxies: str = ""  # comma-separated CIDRs whose X-Forwarded-For is honoured

    # Abuse protection (sliding window, per client IP)
    rate_limit_auth_per_minute: int = 60
    rate_limit_global_per_minute: int = 600

    device_limit_per_user: int = 3
    max_days_offline_sync: int = 90

    seed_on_startup: bool = True

    # Integration layer (FACTORY I/O / TIA Portal / WinCC)
    integrations_enabled: bool = True
    simulated_plant: bool = True

    modbus_enabled: bool = True
    modbus_host: str = "127.0.0.1"
    modbus_port: int = 502

    s7_enabled: bool = False
    s7_ip: str = "192.168.0.1"
    s7_rack: int = 0
    s7_slot: int = 1
    s7_db: int = 1

    opcua_enabled: bool = False
    opcua_url: str = "opc.tcp://127.0.0.1:4840"
    opcua_nodes: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()