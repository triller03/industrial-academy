from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ASAPA - Industrial Automation Training Platform"
    app_version: str = "1.0.0"
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

    # Licensing & plans (blueprint: HWID licensing + tiered plans)
    trial_grace_days: int = 30
    max_free_fault_attempts_per_day: int = 5
    license_length_days: int = 365
    interface_origin: str = ""  # public origin used to build shareable URLs (e.g. https://asapa.app)

    # Billing gateways (blueprint: Stripe + Paynow). Empty = local test gateway.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_map: str = ""  # JSON {"student_pro": "price_xxx", "professional": "...", "institutional": "..."}
    paynow_integration_id: str = ""
    paynow_api_key: str = ""
    paynow_result_url: str = ""

    # TIA Openness bridge (blueprint: hardware-dependent, degrades gracefully)
    tia_openness_enabled: bool = False
    tia_openness_host: str = "127.0.0.1"
    tia_openness_port: int = 8600

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