# Deployment readiness

CodeLabX remains a development/staging candidate. This document prepares a
provider-neutral runtime; it does not declare the application production-ready.

## Local development

Local development continues to use SQLite and `LocMemCache` when `DATABASE_URL`
and `REDIS_URL` are absent. Existing local data is not migrated or modified by
these settings.

## Production runtime dependencies

```bash
python -m pip install -r requirements/prod.txt
```

The production set adds Gunicorn, Psycopg 3, redis-py, and WhiteNoise. Exact
versions are pinned and included in the dependency audit.

## Required backend configuration

Use secret-manager values rather than committing a production environment file.
The following is an example structure, not usable credentials:

```text
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=learn.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://learn.example.com
DATABASE_URL=postgresql://app-user:secret@db.example.com:5432/codelabx?sslmode=verify-full
REDIS_URL=rediss://:secret@cache.example.com:6380/1
DJANGO_USE_WHITENOISE=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_HSTS_SECONDS=31536000
DJANGO_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_HSTS_PRELOAD=True
```

Only enable `DJANGO_TRUST_X_FORWARDED_PROTO=True` when a trusted reverse proxy
sets and strips `X-Forwarded-Proto`. Configure its address through
`GUNICORN_FORWARDED_ALLOW_IPS`; never accept forwarded headers from arbitrary
clients.

## Preflight

The preflight command reports configuration errors without printing credentials:

```bash
python manage.py production_preflight
python manage.py production_preflight --json
python manage.py production_preflight --strict
```

Normal mode blocks on errors. Strict mode also blocks on known warnings. Current
warnings intentionally document unfinished private media storage, bounded legacy
style attributes, background jobs, monitoring, and restore-tested backups.

## Static files and process startup

```bash
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn codelabx.wsgi:application --config gunicorn.conf.py
```

`/live/` checks only that Django can serve a request. `/health/` checks both the
database and cache and returns HTTP 503 when either dependency is unavailable.

## Bounded smoke load

After starting a local or isolated staging instance:

```bash
python scripts/load_smoke.py
python scripts/load_smoke.py --url https://staging.example.com/health/ --allow-remote
```

The script is intentionally capped at 500 requests and 50 workers. It is a smoke
check, not a capacity test. Never point it at a third-party system or production
without explicit authorization.

## Migration and rollback sequence

1. Create and verify an external database and media backup.
2. Restore that backup into an isolated environment.
3. Run `python manage.py migrate --plan` and review the plan.
4. Apply migrations in staging.
5. Run Gate A, production preflight, readiness probes, and the bounded smoke load.
6. Exercise account export/deletion, assessments, XP idempotency, and AI failure
   paths.
7. Record a rollback decision point and practice restoring the backup.

Do not perform a public deployment until private object storage, asynchronous AI
jobs, monitoring/alerting, and backup restoration have been implemented and
validated.
