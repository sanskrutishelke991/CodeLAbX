"""Provider-neutral Gunicorn defaults for CodeLabX."""

from __future__ import annotations

import os


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise RuntimeError(
            f"{name} must be between {minimum} and {maximum}."
        )
    return parsed


bind = f"0.0.0.0:{env_int('PORT', 8000, 1, 65535)}"
workers = env_int("WEB_CONCURRENCY", 2, 1, 32)
threads = env_int("GUNICORN_THREADS", 4, 1, 32)
worker_class = "gthread"
timeout = env_int("GUNICORN_TIMEOUT_SECONDS", 60, 10, 600)
graceful_timeout = env_int("GUNICORN_GRACEFUL_TIMEOUT_SECONDS", 30, 5, 300)
keepalive = env_int("GUNICORN_KEEPALIVE_SECONDS", 5, 1, 120)
max_requests = env_int("GUNICORN_MAX_REQUESTS", 1000, 0, 1_000_000)
max_requests_jitter = env_int("GUNICORN_MAX_REQUESTS_JITTER", 100, 0, 100_000)
accesslog = "-"
errorlog = "-"
capture_output = True
forwarded_allow_ips = os.getenv(
    "GUNICORN_FORWARDED_ALLOW_IPS",
    "127.0.0.1",
)
