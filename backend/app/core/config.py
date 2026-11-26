"""Application settings, read from environment variables.

A local `backend/.env` file is loaded if present (without overriding real
environment variables). Required secrets have no defaults: the app refuses
to start without them rather than falling back to something insecure.
"""

import ipaddress
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEV_MAIL_DIR = Path(__file__).resolve().parents[2] / ".dev-mail"


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
class RateLimitPolicy:
    """At most `limit` events per fixed window of `window` seconds."""

    name: str
    limit: int
    window: int


IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Initial limits. Override with e.g. OPENCAMPUS_RATE_LIMIT_LOGIN_IP="5/60,20/3600".
DEFAULT_RATE_LIMITS = {
    "login_ip": "5/60,20/3600",
    "login_account": "5/900,20/3600",  # failed attempts per account identifier
    "register_ip": "3/3600",
    "refresh_session": "30/60,120/3600",
    "refresh_ip": "120/60,1200/3600",  # generous: many students can share one NAT address
    "reset_request_ip": "5/900,20/3600",
    "reset_request_account": "3/3600",  # per email, counted whether or not the account exists
    "reset_confirm_ip": "10/900,30/3600",
}


def _policies(group: str) -> tuple[RateLimitPolicy, ...]:
    raw = os.getenv(f"OPENCAMPUS_RATE_LIMIT_{group.upper()}", DEFAULT_RATE_LIMITS[group])
    policies = []
    for item in _split_csv(raw):
        try:
            limit_text, window_text = item.split("/")
            limit, window = int(limit_text), int(window_text)
        except ValueError:
            raise ConfigError(f"OPENCAMPUS_RATE_LIMIT_{group.upper()}: expected 'limit/seconds,...', got {item!r}") from None
        if limit < 1 or window < 1:
            raise ConfigError(f"OPENCAMPUS_RATE_LIMIT_{group.upper()}: limit and window must be positive")
        policies.append(RateLimitPolicy(name=f"{group}:{window}", limit=limit, window=window))
    if not policies or len({p.window for p in policies}) != len(policies):
        raise ConfigError(f"OPENCAMPUS_RATE_LIMIT_{group.upper()}: give at least one policy, one per window size")
    return tuple(policies)


def _networks(name: str) -> tuple[IPNetwork, ...]:
    try:
        return tuple(ipaddress.ip_network(item, strict=False) for item in _split_csv(os.getenv(name, "")))
    except ValueError as exc:
        raise ConfigError(f"{name}: {exc}") from None


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

    rate_limit_secret: str
    trusted_proxies: tuple[IPNetwork, ...]
    rl_login_ip: tuple[RateLimitPolicy, ...]
    rl_login_account: tuple[RateLimitPolicy, ...]
    rl_register_ip: tuple[RateLimitPolicy, ...]
    rl_refresh_session: tuple[RateLimitPolicy, ...]
    rl_refresh_ip: tuple[RateLimitPolicy, ...]
    rl_reset_request_ip: tuple[RateLimitPolicy, ...]
    rl_reset_request_account: tuple[RateLimitPolicy, ...]
    rl_reset_confirm_ip: tuple[RateLimitPolicy, ...]

    # Open registration: sign-ups without an institution join this one.
    # Empty = institution code required (production default).
    open_registration_slug: str
    open_registration_name: str

    # Password recovery and email
    frontend_url: str
    password_reset_ttl: int
    email_mode: str  # "dev_file" | "smtp"
    email_from: str
    email_dev_dir: Path
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str = field(repr=False, default="")  # never printed with the settings
    smtp_tls: str = "starttls"  # "starttls" | "ssl" | "none"

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

    rate_limit_secret = _required("OPENCAMPUS_RATE_LIMIT_SECRET")
    if len(rate_limit_secret) < 32:
        raise ConfigError("OPENCAMPUS_RATE_LIMIT_SECRET must be at least 32 characters")
    if rate_limit_secret == jwt_secret:
        raise ConfigError("OPENCAMPUS_RATE_LIMIT_SECRET must differ from OPENCAMPUS_JWT_SECRET")

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
        rate_limit_secret=rate_limit_secret,
        trusted_proxies=_networks("OPENCAMPUS_TRUSTED_PROXIES"),
        rl_login_ip=_policies("login_ip"),
        rl_login_account=_policies("login_account"),
        rl_register_ip=_policies("register_ip"),
        rl_refresh_session=_policies("refresh_session"),
        rl_refresh_ip=_policies("refresh_ip"),
        rl_reset_request_ip=_policies("reset_request_ip"),
        rl_reset_request_account=_policies("reset_request_account"),
        rl_reset_confirm_ip=_policies("reset_confirm_ip"),
        open_registration_slug=_open_registration_slug(environment),
        open_registration_name=os.getenv("OPENCAMPUS_OPEN_REGISTRATION_NAME", "OpenCampus Community").strip()
        or "OpenCampus Community",
        frontend_url=_frontend_url(environment),
        password_reset_ttl=_int("OPENCAMPUS_PASSWORD_RESET_TTL_SECONDS", 30 * 60),
        **_email(environment),
    )


def _open_registration_slug(environment: str) -> str:
    # On by default for local development; must be switched on explicitly in production.
    slug = os.getenv("OPENCAMPUS_OPEN_REGISTRATION", "" if environment == "production" else "opencampus").strip().lower()
    if slug and not re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", slug):
        raise ConfigError("OPENCAMPUS_OPEN_REGISTRATION must be a valid institution slug (lowercase letters, digits, hyphens)")
    return slug


def _frontend_url(environment: str) -> str:
    raw = os.getenv("OPENCAMPUS_FRONTEND_URL", "" if environment == "production" else "http://localhost:5173").strip()
    if not raw:
        raise ConfigError("OPENCAMPUS_FRONTEND_URL must be set in production (used to build password-reset links)")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment:
        raise ConfigError("OPENCAMPUS_FRONTEND_URL must be an absolute http(s) URL without query or fragment")
    if environment == "production" and parts.scheme != "https":
        raise ConfigError("OPENCAMPUS_FRONTEND_URL must use https in production")
    return raw.rstrip("/")


def _email(environment: str) -> dict:
    """Email delivery settings. Development defaults to a local file sink;
    production must use SMTP with TLS and can never fall back to the sink."""
    smtp_host = os.getenv("OPENCAMPUS_SMTP_HOST", "").strip()
    default_mode = "smtp" if smtp_host or environment == "production" else "dev_file"
    mode = os.getenv("OPENCAMPUS_EMAIL_MODE", default_mode).strip().lower()
    if mode not in {"dev_file", "smtp"}:
        raise ConfigError("OPENCAMPUS_EMAIL_MODE must be 'dev_file' or 'smtp'")
    if mode == "dev_file" and environment == "production":
        raise ConfigError("OPENCAMPUS_EMAIL_MODE=dev_file is not allowed in production")

    tls = os.getenv("OPENCAMPUS_SMTP_TLS", "starttls").strip().lower()
    if tls not in {"starttls", "ssl", "none"}:
        raise ConfigError("OPENCAMPUS_SMTP_TLS must be 'starttls', 'ssl' or 'none'")
    try:
        port = int(os.getenv("OPENCAMPUS_SMTP_PORT", "465" if tls == "ssl" else "587"))
    except ValueError:
        raise ConfigError("OPENCAMPUS_SMTP_PORT must be a number") from None
    if not 0 < port < 65536:
        raise ConfigError("OPENCAMPUS_SMTP_PORT must be between 1 and 65535")

    email_from = os.getenv("OPENCAMPUS_EMAIL_FROM", "" if mode == "smtp" else "OpenCampus <no-reply@localhost>").strip()
    username = os.getenv("OPENCAMPUS_SMTP_USERNAME", "").strip()
    password = os.getenv("OPENCAMPUS_SMTP_PASSWORD", "")
    if mode == "smtp":
        if not smtp_host:
            raise ConfigError("OPENCAMPUS_SMTP_HOST is required when OPENCAMPUS_EMAIL_MODE=smtp")
        if not email_from:
            raise ConfigError("OPENCAMPUS_EMAIL_FROM is required when OPENCAMPUS_EMAIL_MODE=smtp")
        if environment == "production" and tls == "none":
            raise ConfigError("OPENCAMPUS_SMTP_TLS=none is not allowed in production")
        if bool(username) != bool(password):
            raise ConfigError("Set both OPENCAMPUS_SMTP_USERNAME and OPENCAMPUS_SMTP_PASSWORD, or neither")
        if password and tls == "none":
            raise ConfigError("Refusing to send SMTP credentials without TLS (OPENCAMPUS_SMTP_TLS=none)")

    return {
        "email_mode": mode,
        "email_from": email_from,
        "email_dev_dir": Path(os.getenv("OPENCAMPUS_EMAIL_DEV_DIR", str(DEV_MAIL_DIR))),
        "smtp_host": smtp_host,
        "smtp_port": port,
        "smtp_username": username,
        "smtp_password": password,
        "smtp_tls": tls,
    }


@lru_cache
def get_settings() -> Settings:
    return build_settings()
