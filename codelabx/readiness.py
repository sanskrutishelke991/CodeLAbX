"""Production preflight checks that do not reveal configured secrets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _local_host(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    return normalized in {
        "localhost",
        "127.0.0.1",
        "::1",
        "testserver",
    }


def collect_production_findings(config) -> list[Finding]:
    """Return actionable errors and warnings for a settings-like object."""
    findings: list[Finding] = []

    def error(code: str, message: str) -> None:
        findings.append(Finding("error", code, message))

    def warning(code: str, message: str) -> None:
        findings.append(Finding("warning", code, message))

    if bool(getattr(config, "DEBUG", True)):
        error("PRD001", "DJANGO_DEBUG must be False.")

    secret = str(getattr(config, "SECRET_KEY", ""))
    weak_markers = (
        "replace-with",
        "verification-only",
        "django-insecure",
        "not-for-production",
    )
    if len(secret) < 50 or any(marker in secret.lower() for marker in weak_markers):
        error("PRD002", "DJANGO_SECRET_KEY must be a strong production-only value.")

    allowed_hosts = list(getattr(config, "ALLOWED_HOSTS", []))
    if not allowed_hosts or "*" in allowed_hosts:
        error("PRD003", "DJANGO_ALLOWED_HOSTS must use explicit production hosts.")
    elif not any(not _local_host(host) for host in allowed_hosts):
        error("PRD003", "DJANGO_ALLOWED_HOSTS needs at least one non-local host.")

    csrf_origins = list(getattr(config, "CSRF_TRUSTED_ORIGINS", []))
    if not csrf_origins:
        error("PRD004", "Configure at least one HTTPS CSRF trusted origin.")
    elif any(urlsplit(origin).scheme != "https" for origin in csrf_origins):
        error("PRD004", "Every CSRF trusted origin must use HTTPS.")

    required_booleans = [
        ("SECURE_SSL_REDIRECT", "PRD005", "Enable HTTPS redirection."),
        ("SESSION_COOKIE_SECURE", "PRD006", "Secure the session cookie."),
        ("CSRF_COOKIE_SECURE", "PRD007", "Secure the CSRF cookie."),
        ("RATE_LIMIT_ENABLED", "PRD008", "Keep request throttling enabled."),
    ]
    for name, code, message in required_booleans:
        if not bool(getattr(config, name, False)):
            error(code, message)

    if int(getattr(config, "SECURE_HSTS_SECONDS", 0)) < 31_536_000:
        error("PRD009", "Use an HSTS duration of at least one year after HTTPS validation.")
    if not bool(getattr(config, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False)):
        warning("PRD-W001", "HSTS does not include subdomains.")
    if not bool(getattr(config, "SECURE_HSTS_PRELOAD", False)):
        warning("PRD-W002", "HSTS preload is not enabled.")

    databases = getattr(config, "DATABASES", {})
    database = databases.get("default", {})
    if database.get("ENGINE") != "django.db.backends.postgresql":
        error("PRD010", "Use PostgreSQL for a production deployment.")
    elif bool(getattr(config, "DATABASE_REQUIRE_TLS", True)):
        sslmode = database.get("OPTIONS", {}).get("sslmode")
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            error("PRD011", "PostgreSQL must use a TLS-enforcing sslmode.")

    caches = getattr(config, "CACHES", {})
    cache = caches.get("default", {})
    if cache.get("BACKEND") != "django.core.cache.backends.redis.RedisCache":
        error("PRD012", "Use a shared Redis cache for distributed throttling.")
    elif bool(getattr(config, "REDIS_REQUIRE_TLS", True)):
        location = str(cache.get("LOCATION", ""))
        if urlsplit(location).scheme != "rediss":
            error("PRD013", "Redis must use rediss:// when TLS is required.")

    if not bool(getattr(config, "USE_WHITENOISE", False)):
        error("PRD014", "Enable WhiteNoise for the current static-file strategy.")
    static_backend = (
        getattr(config, "STORAGES", {})
        .get("staticfiles", {})
        .get("BACKEND", "")
    )
    accepted_static_backends = {
        "codelabx.storage.CodeLabXStaticFilesStorage",
        "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
    if static_backend not in accepted_static_backends:
        error("PRD015", "Use compressed manifest storage for production static files.")

    email_backend = str(getattr(config, "EMAIL_BACKEND", ""))
    if any(
        backend in email_backend
        for backend in ("console", "locmem", "dummy")
    ):
        error("PRD016", "Configure a transactional production email backend.")
    if "localhost" in str(getattr(config, "DEFAULT_FROM_EMAIL", "")).lower():
        error("PRD017", "Configure a verified non-local default sender address.")

    ai_enabled = any(
        bool(getattr(config, name, False))
        for name in (
            "AI_FEATURES_ENABLED",
            "ASSESSMENTS_ENABLED",
            "CODING_CHALLENGES_ENABLED",
            "IMAGE_ANALYSIS_ENABLED",
        )
    )
    if ai_enabled and not getattr(config, "GEMINI_API_KEY", None):
        error("PRD018", "Enabled AI features require GEMINI_API_KEY.")

    default_storage = (
        getattr(config, "STORAGES", {})
        .get("default", {})
        .get("BACKEND", "")
    )
    if default_storage == "django.core.files.storage.FileSystemStorage":
        warning(
            "PRD-W003",
            "User media still uses local filesystem storage; private object storage is pending.",
        )
    if bool(getattr(config, "CSP_LEGACY_INLINE_ALLOWED", True)):
        warning(
            "PRD-W004",
            "CSP still permits legacy inline scripts and styles.",
        )
    if not bool(getattr(config, "TRUST_X_FORWARDED_PROTO", False)):
        warning(
            "PRD-W005",
            "Proxy HTTPS trust is disabled; enable it only for a trusted terminating proxy.",
        )
    warning(
        "PRD-W006",
        "Background AI jobs, error monitoring, and restore-tested backups remain pending.",
    )

    return findings
