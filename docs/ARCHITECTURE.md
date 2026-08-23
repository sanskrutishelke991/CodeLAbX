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
- Installable PWA shell plus browser-native Web Speech output/input controls
- Django i18n with English, Hindi, and Marathi core-control catalogs
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
| `accounts` | Authentication, profiles, privacy controls, email preferences, deterministic weekly reports, export, deletion |
| `dashboard` | Public landing/legal pages and the signed-in verified activity overview |
| `learning` | ML, DSA, and Django/full-stack roadmap generation, daily lessons, lifecycle actions, day completion |
| `content` | Curated video categories, library, favorites, and watched state |
| `practice` | Practice-problem generation and non-executing AI code review |
| `assessments` | Generated MCQs, server-timed attempts, authoritative scoring |
| `ai_tools` | Gemini adapter, chat, image analysis, request guards, sanitization |
| `progress` | XP ledger, levels, streaks, badges, activity, analytics, leaderboard |
| `notes` | Owner-scoped notes and validated bookmarks |
| `challenges` | Global scheduled challenges, owner-scoped attempts, AI feedback |
| `intelligence` | Learning DNA, Skill Passport, retention, adaptive routes, and user-controlled tutor context |

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
Existing Roadmap/Day rows remain unchanged. Transaction-on-commit emitters and
curated routing/goal diagnostics feed the private Learning DNA and evidence
explorer. Prerequisite-aware bottleneck analysis creates persisted, idempotent
Mission proposals with deterministic reason codes. Freshness is calculated for
the current view without rewriting historical evidence. Sprint 4 adds
RoadmapRevision/RoadmapNode sidecars: route changes show an exact diff and require
an explicit accept, reject, or postpone decision. Legacy Day rows remain unchanged,
user-pinned nodes keep their position, and superseded revisions can be restored as
new revisions. Sprint 5 adds explicit tutor modes, bounded learner-visible memory,
manual session summaries, and feedback suggestions only after repeated signals and
an explicit adaptation opt-in. The AI chat context includes accepted missions and
evidence-backed states, frames all learner-written memory as untrusted data, and
never fine-tunes a per-user model. The private Skill Passport projects the same
ledger into source-separated, evidence-observed skill cards; it does not claim
independent verification. The Retention Center recomputes time-current freshness
and can propose one deterministic refresh Mission without rewriting mastery or
displacing existing active work.

### Email and weekly reports

Email reports are explicit opt-in account features. The weekly report renderer
queries authoritative activity, assessment, challenge, evidence, Passport, mission,
and retention rows without AI-generated claims. `WeeklyReportDelivery` stores only
period/status/hash metadata and prevents duplicate scheduled delivery. Preview
emails are separate and do not consume a scheduled period. Development defaults to
the console backend; real inbox delivery requires a transactional provider. An
external scheduler must invoke `python manage.py send_weekly_reports` or enqueue its
maintenance task.

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
3. Build only bounded, owner-scoped tutor context; frame learner memory as data,
   never higher-priority instructions.
4. Send the minimum relevant prompt or normalized image to Gemini.
5. Treat provider output as untrusted.
6. Validate structured JSON or sanitize Markdown/HTML.
7. Store only owner-scoped records and return generic public failures.

AI code review is feedback, not code execution or a correctness verdict. Coding
challenges never award "correct" status based on model prose.

## Static and media files

Bootstrap, icons, and Chart.js are served from `static/vendor/`. WhiteNoise's
manifest storage is optional and verified by Gate A's production collectstatic
step. Optional upstream source-map comments are ignored because maps are not
runtime dependencies.

The root-scoped service worker precaches only the generic `/offline/` response and
versioned `/static/` assets. Navigation requests are network-only with the generic
offline fallback; authenticated HTML, APIs, media, chats, and user records are never
written to Cache Storage. PWA installation still requires HTTPS outside localhost.
Text-to-speech runs through the browser Web Speech API, reads bounded `textContent`,
and stores only voice/rate preferences locally. Voice coding input uses explicit
browser microphone permission, inserts at most 4,000 transcript characters into a
focused writable field, and stores no audio in CodeLabX; browser/OS speech vendors
may process audio under their own policies. LocaleMiddleware and compiled gettext
catalogs translate core navigation and accessibility controls into Hindi and
Marathi. Remaining legacy page copy is still English and tracked as explicit debt.

User media still uses local filesystem storage. This is development-only. A
private object-storage backend with authenticated delivery remains a production
blocker.

## Operational interfaces

- `/live/` proves that the Django process can answer.
- `/health/` checks database and cache read/write readiness and fails with 503.
- `python manage.py production_preflight` reports secret-safe configuration
  blockers.
- `python manage.py send_weekly_reports --dry-run` previews scheduler eligibility;
  actual recurring execution still requires an external scheduler.
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
- PWA offline mode intentionally does not make private learner data available offline.
- Text-to-speech and speech-recognition availability depend on the browser/OS;
  some browsers route recognition through their own cloud service.
- Hindi/Marathi coverage currently targets core navigation and accessibility
  controls rather than every legacy page.
- No staging provider, monitoring vendor, or production email service is chosen.
- PostgreSQL/Redis support is configured and tested, but no real production data
  migration has been performed.

See `docs/DEPLOYMENT_READINESS.md` for the staging and rollback gates.
