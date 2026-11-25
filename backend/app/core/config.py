"""Application settings, read from environment variables.

A local `backend/.env` file is loaded if present (without overriding real
environment variables). Required secrets have no defaults: the app refuses
to start without them rather than falling back to something insecure.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class ConfigError(RuntimeError):
    pass


def load_env_file(path: Path = ENV_FILE) -> None:
    """Minimal KEY=VALUE loader; real environment variables win."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} must be set (see backend/.env.example)")
    return value


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    app_name: str
    version: str
    environment: str
    cors_origins: list[str]

    database_url: str
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    access_token_ttl: int
    refresh_token_ttl: int
    session_max_age: int
    refresh_reuse_grace: int

    cookie_secure: bool
    cookie_samesite: str
    refresh_cookie_name: str
    csrf_cookie_name: str

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def build_settings() -> Settings:
    load_env_file()
    environment = os.getenv("OPENCAMPUS_ENV", "development")

    jwt_secret = _required("OPENCAMPUS_JWT_SECRET")
    if len(jwt_secret) < 32:
        raise ConfigError("OPENCAMPUS_JWT_SECRET must be at least 32 characters")

    cookie_secure = _bool("OPENCAMPUS_COOKIE_SECURE", True)
    if environment == "production" and not cookie_secure:
        raise ConfigError("OPENCAMPUS_COOKIE_SECURE cannot be false in production")

    samesite = os.getenv("OPENCAMPUS_COOKIE_SAMESITE", "strict").lower()
    if samesite not in {"strict", "lax"}:
        raise ConfigError("OPENCAMPUS_COOKIE_SAMESITE must be 'strict' or 'lax'")

    return Settings(
        app_name="OpenCampus API",
        version="0.2.0",
        environment=environment,
        cors_origins=_split_csv(os.getenv("OPENCAMPUS_CORS_ORIGINS", "http://localhost:5173")),
        database_url=_required("OPENCAMPUS_DATABASE_URL"),
        jwt_secret=jwt_secret,
        jwt_issuer="opencampus",
        jwt_audience="opencampus-api",
        access_token_ttl=_int("OPENCAMPUS_ACCESS_TOKEN_TTL_SECONDS", 10 * 60),
        refresh_token_ttl=_int("OPENCAMPUS_REFRESH_TOKEN_TTL_SECONDS", 7 * 24 * 3600),
        session_max_age=_int("OPENCAMPUS_SESSION_MAX_AGE_SECONDS", 30 * 24 * 3600),
        refresh_reuse_grace=_int("OPENCAMPUS_REFRESH_REUSE_GRACE_SECONDS", 20),
        cookie_secure=cookie_secure,
        cookie_samesite=samesite,
        # __Secure- prefix makes browsers reject the cookie unless it is Secure.
        refresh_cookie_name="__Secure-oc_refresh" if cookie_secure else "oc_refresh",
        csrf_cookie_name="__Secure-oc_csrf" if cookie_secure else "oc_csrf",
    )


@lru_cache
def get_settings() -> Settings:
    return build_settings()
