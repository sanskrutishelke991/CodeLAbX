# CodeLabX architecture

Last reviewed: 2026-08-08

## Status

CodeLabX is a modular Django monolith under stabilization. It is suitable for
local development and controlled staging evaluation, not a public production
launch. The monolith is intentional: the current scale and team do not justify
microservices.

## Runtime stack

- Python 3.12 or 3.14
- Django 6.0.8
- Django templates, Bootstrap 5.3.8, Bootstrap Icons 1.13.1, and vanilla JS
- SQLite and process-local cache by default for development
- Optional PostgreSQL, Redis, WhiteNoise, and Gunicorn configuration for staging
- Google Gemini through `google-genai` for explicitly enabled AI features
- Markdown plus `nh3` for allowlisted AI HTML rendering
- Pillow for validated and normalized image uploads

Exact Python package versions are in `requirements/`. Browser dependency
versions and hashes are in `static/vendor/manifest.json`.

## Application boundaries

| App | Responsibility |
| --- | --- |
| `accounts` | Registration, authentication throttling, profiles, settings, password reset, export, deletion |
| `dashboard` | Public landing/legal pages and the signed-in verified activity overview |
| `learning` | ML/DSA roadmap generation, daily lessons, lifecycle actions, day completion |
| `content` | Curated video categories, library, favorites, and watched state |
| `practice` | Practice-problem generation and non-executing AI code review |
| `assessments` | Generated MCQs, server-timed attempts, authoritative scoring |
| `ai_tools` | Gemini adapter, chat, image analysis, request guards, sanitization |
| `progress` | XP ledger, levels, streaks, badges, activity, analytics, leaderboard |
| `notes` | Owner-scoped notes and validated bookmarks |
| `challenges` | Global scheduled challenges, owner-scoped attempts, AI feedback |
| `intelligence` | Versioned Skill Packs, immutable evidence ledger, deterministic SkillState snapshots |

Django's built-in authentication, admin, sessions, messages, staticfiles, and
content-types apps remain shared platform services.

## Request architecture

```text
Browser
  -> Django security/session/CSRF/auth middleware
  -> app URL and view
  -> validation and authorization
  -> service/ORM operation
  -> template or bounded JSON response
```

State-changing browser operations use POST and CSRF protection. User-owned
objects are always filtered by the signed-in user. Operational responses receive
security headers from `SecurityHeadersMiddleware`.

## Data architecture

Django models and migrations are the schema source of truth. Development uses
SQLite when `DATABASE_URL` is absent. A validated PostgreSQL URL can be supplied
without changing application code. Connection lifetime, health checks, timeout,
and TLS mode are bounded through environment settings.

XP is append-only at the event level through `XPTransaction` idempotency keys.
Summary models such as `UserLevel`, `UserStreak`, and `DailyActivity` are updated
by service functions in database transactions.

### Learning Intelligence foundation

The `intelligence` app is a sidecar to existing roadmaps. It loads reviewed,
versioned Programming/DSA, ML, and Django Skill Packs; records immutable,
idempotent `LearningEvent` evidence; and derives rebuildable `SkillState`
mastery, confidence, and freshness values without AI-generated numeric scores.
Existing Roadmap/Day rows remain unchanged in Sprint 1. See
`docs/LEARNING_INTELLIGENCE_V1.md` for the adaptive roadmap and tutor plan.

## Cache and throttling

Without `REDIS_URL`, local development uses `LocMemCache`. This is intentionally
process-local and not acceptable for distributed production throttling. With a
validated `redis://` or `rediss://` URL, Django's Redis backend provides shared
AI/auth request counters and readiness checks. Cache errors are not silently
ignored.

## AI trust boundary

AI features are disabled unless their environment flags and API key are set.
The normal flow is:

1. Validate content type, body size, fields, and feature flags.
2. Apply cache-backed burst and daily limits.
3. Send the minimum relevant prompt or normalized image to Gemini.
4. Treat provider output as untrusted.
5. Validate structured JSON or sanitize Markdown/HTML.
6. Store only owner-scoped records and return generic public failures.

AI code review is feedback, not code execution or a correctness verdict. Coding
challenges never award "correct" status based on model prose.

## Static and media files

Bootstrap, icons, and Chart.js are served from `static/vendor/`. WhiteNoise's
manifest storage is optional and verified by Gate A's production collectstatic
step. Optional upstream source-map comments are ignored because maps are not
runtime dependencies.

User media still uses local filesystem storage. This is development-only. A
private object-storage backend with authenticated delivery remains a production
blocker.

## Operational interfaces

- `/live/` proves that the Django process can answer.
- `/health/` checks database and cache read/write readiness and fails with 503.
- `python manage.py production_preflight` reports secret-safe configuration
  blockers.
- `python scripts/verify.py` runs compilation, critical lint, migration drift,
  tests, coverage, static collection, deploy checks, and dependency audit.
- `python scripts/load_smoke.py` performs a deliberately bounded smoke load.

## Known architectural limits

- Django's Tasks contract is configured with immediate local execution; a durable
  third-party backend and worker are still required for production.
- Daily challenge generation can be enqueued safely, but an external scheduler
  must invoke the enqueue command.
- Local user media is not private production storage.
- CSP blocks inline scripts and handlers; legacy style attributes remain temporarily allowed.
- No staging provider, monitoring vendor, or production email service is chosen.
- PostgreSQL/Redis support is configured and tested, but no real production data
  migration has been performed.

See `docs/DEPLOYMENT_READINESS.md` for the staging and rollback gates.
