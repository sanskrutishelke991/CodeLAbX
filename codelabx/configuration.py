"""Provider-neutral database and cache configuration helpers."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

_POSTGRES_SCHEMES = {"postgres", "postgresql"}
_POSTGRES_SSL_MODES = {
    "disable",
    "allow",
    "prefer",
    "require",
    "verify-ca",
    "verify-full",
}
_REDIS_SCHEMES = {"redis", "rediss"}
_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_CACHE_PREFIX = re.compile(r"^[A-Za-z0-9:_-]{1,64}$")


def _decode_url_part(value: str, label: str) -> str:
    if _PERCENT_ESCAPE.search(value):
        raise ImproperlyConfigured(
            f"DATABASE_URL contains invalid percent encoding in {label}."
        )
    return unquote(value)


def build_database_settings(
    *,
    base_dir: Path,
    database_url: str,
    sqlite_path: str,
    connection_max_age: int,
    connect_timeout: int,
) -> dict[str, dict[str, object]]:
    """Build Django DATABASES while keeping SQLite as the local default."""
    if connection_max_age < 0:
        raise ImproperlyConfigured(
            "DJANGO_DB_CONN_MAX_AGE must be zero or greater."
        )
    if connect_timeout < 1:
        raise ImproperlyConfigured(
            "DJANGO_DB_CONNECT_TIMEOUT_SECONDS must be at least 1."
        )

    database_url = database_url.strip()
    if not database_url:
        if sqlite_path == ":memory:":
            name: Path | str = sqlite_path
        else:
            name = Path(sqlite_path)
            if not name.is_absolute():
                name = base_dir / name
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": name,
            }
        }

    try:
        parsed = urlsplit(database_url)
        port = parsed.port
        hostname = parsed.hostname
    except ValueError as exc:
        raise ImproperlyConfigured(
            "DATABASE_URL has an invalid host or port."
        ) from exc

    if parsed.scheme.lower() not in _POSTGRES_SCHEMES:
        raise ImproperlyConfigured(
            "DATABASE_URL must use postgresql:// or postgres://."
        )
    if not hostname:
        raise ImproperlyConfigured("DATABASE_URL must include a host.")
    if parsed.fragment:
        raise ImproperlyConfigured("DATABASE_URL must not contain a fragment.")

    raw_name = parsed.path.removeprefix("/")
    if not raw_name:
        raise ImproperlyConfigured("DATABASE_URL must include a database name.")
    name = _decode_url_part(raw_name, "database name")
    if "/" in name:
        raise ImproperlyConfigured(
            "DATABASE_URL database name must not contain a slash."
        )

    try:
        query_items = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise ImproperlyConfigured(
            "DATABASE_URL contains an invalid query string."
        ) from exc

    query: dict[str, str] = {}
    for key, value in query_items:
        if key != "sslmode":
            raise ImproperlyConfigured(
                f"DATABASE_URL query option {key!r} is not supported."
            )
        if key in query:
            raise ImproperlyConfigured(
                "DATABASE_URL must not repeat the sslmode option."
            )
        query[key] = value

    sslmode = query.get("sslmode")
    if sslmode and sslmode not in _POSTGRES_SSL_MODES:
        raise ImproperlyConfigured(
            "DATABASE_URL sslmode is not a recognized PostgreSQL mode."
        )

    options: dict[str, object] = {"connect_timeout": connect_timeout}
    if sslmode:
        options["sslmode"] = sslmode

    username = _decode_url_part(parsed.username or "", "username")
    password = _decode_url_part(parsed.password or "", "password")

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": name,
            "USER": username,
            "PASSWORD": password,
            "HOST": hostname,
            "PORT": str(port or 5432),
            "CONN_MAX_AGE": connection_max_age,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": options,
        }
    }


def build_cache_settings(
    *,
    redis_url: str,
    key_prefix: str,
    default_timeout: int,
    socket_timeout: int,
) -> dict[str, dict[str, object]]:
    """Build a shared Redis cache or a process-local development fallback."""
    if not _CACHE_PREFIX.fullmatch(key_prefix):
        raise ImproperlyConfigured(
            "DJANGO_CACHE_KEY_PREFIX may contain only letters, numbers, :, _, and -."
        )
    if default_timeout < 1:
        raise ImproperlyConfigured(
            "DJANGO_CACHE_DEFAULT_TIMEOUT must be at least 1."
        )
    if socket_timeout < 1:
        raise ImproperlyConfigured(
            "DJANGO_CACHE_SOCKET_TIMEOUT_SECONDS must be at least 1."
        )

    redis_url = redis_url.strip()
    if not redis_url:
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "codelabx-development-security-cache",
                "KEY_PREFIX": key_prefix,
                "TIMEOUT": default_timeout,
            }
        }

    try:
        parsed = urlsplit(redis_url)
        _ = parsed.port
    except ValueError as exc:
        raise ImproperlyConfigured(
            "REDIS_URL has an invalid host or port."
        ) from exc

    if parsed.scheme.lower() not in _REDIS_SCHEMES:
        raise ImproperlyConfigured(
            "REDIS_URL must use redis:// or rediss://."
        )
    if not parsed.hostname:
        raise ImproperlyConfigured("REDIS_URL must include a host.")
    if parsed.fragment:
        raise ImproperlyConfigured("REDIS_URL must not contain a fragment.")

    return {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": key_prefix,
            "TIMEOUT": default_timeout,
            "OPTIONS": {
                "socket_connect_timeout": socket_timeout,
                "socket_timeout": socket_timeout,
                "health_check_interval": 30,
            },
        }
    }
