# CodeLabX

CodeLabX is a Django learning platform with personalized roadmaps, verified XP, assessments, challenges, notes, video progress, AI-assisted learning, and analytics.

## Current status

The project is under active stabilization on `stabilization/production-readiness`. It is suitable for local development and staging evaluation, not public production deployment yet.

## Requirements

- Python 3.12 or 3.14
- SQLite for local development
- A Gemini API key for optional AI features

## Setup

```bash
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_badges
python manage.py seed_videos
python manage.py createsuperuser
python manage.py runserver
```

Set a new random `DJANGO_SECRET_KEY` and your optional `GEMINI_API_KEY` in `.env`. Never commit `.env`.

## Verification

```bash
python scripts/verify.py
```

The gate runs compilation, critical Ruff checks, migration-drift detection, Django checks, the complete test suite, coverage, deployment checks, and dependency auditing.

## Useful commands

```bash
python manage.py generate_daily_challenges
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
```

## Main applications

- `accounts` — authentication, profiles, reset/export/deletion
- `learning` — roadmaps and daily lessons
- `assessments` — generated tests and authoritative attempts
- `challenges` — scheduled theory challenges and AI code feedback
- `ai_tools` — safe Gemini rendering, chat, and image analysis
- `progress` — activity, streaks, badges, levels, XP ledger, analytics
- `content` — video library and watched/favorite state
- `notes` — private notes and bookmarks
- `dashboard` — verified learning overview

## Security baseline

- Environment-based secrets and deployment settings
- Sanitized AI HTML
- Request validation and AI quotas
- Verified image decoding and normalization
- Authentication throttling
- POST-only state changes
- Idempotent XP transactions
- Server-controlled assessment timing
- Privacy-scoped profiles, chats, and leaderboards
- Self-hosted, version-pinned browser dependencies
- Enforced origin-restricting CSP (legacy inline allowances remain)

## Frontend dependencies

Bootstrap, Bootstrap Icons, and Chart.js are checked into `static/vendor/` with exact versions, SHA-256 digests, and upstream MIT licenses. Pages do not fetch those runtime assets from a third-party CDN.

## Data backup

Before schema or destructive changes, copy `db.sqlite3`, archive `media/`, and create a validated `dumpdata` export outside the repository.

## Deployment

Production deployment is intentionally deferred until PostgreSQL, Redis-backed limits/jobs, private object storage, monitoring, and a staging rollback test are complete.
