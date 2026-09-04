from typing import Literal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Environment ──────────────────────────────────────────
    environment: str = "development"

    # ── Database ─────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres"
        "@localhost:5432/isp_ticketing"
    )

    # ── JWT ──────────────────────────────────────────────────
    jwt_secret_key: str = "change-this-to-a-long-random-string"
    jwt_algorithm: str = "HS256"

    # Clients authenticate via Google and stay signed in longer.
    client_access_token_expire_minutes: int = 60
    client_refresh_token_expire_days: int = 7

    # Manager / super_admin sessions are shorter lived by design.
    admin_access_token_expire_minutes: int = 60
    admin_refresh_token_expire_hours: int = 24

    # ── Google OAuth ─────────────────────────────────────────
    google_client_id: str = ""

    # ── Cookies ──────────────────────────────────────────────
    cookie_domain: str = "localhost"

    # ── Rate limiting ────────────────────────────────────────
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "5/minute"

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = [
        "http://localhost:5173",
    ]

    # ── Trusted hosts ────────────────────────────────────────
    allowed_hosts: list[str] = ["*"]

    # ── VAPID (Web Push) ────────────────────────────────────
    vapid_private_key: str = ""
    vapid_claims_email: str = "mailto:support@pnet-client.com"

    # ── Computed ─────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def vapid_claims(self) -> dict:
        return {"sub": self.vapid_claims_email}

    @property
    def cookie_samesite(self) -> Literal["lax", "none"]:
        return "none" if self.is_production else "lax"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so .env is only parsed once."""
    return Settings()