# CodeLabX stabilization backlog

Last reviewed: 2026-08-08

This is a dependency-ordered engineering backlog, not a fictional delivery
schedule. Completed work remains in Git history and regression tests.

## Completed stabilization foundation

- Minimal pinned base/dev/production requirement sets and dependency audit
- Environment-driven secrets, hosts, CSRF, TLS, cookies, HSTS, logging, and flags
- Gate A CI on Python 3.12 and 3.14
- Sanitized AI Markdown/HTML and bounded JSON/image inputs
- Feature guards, daily/burst limits, and Redis-ready shared cache configuration
- Owner-scoped records, auth throttling, POST-only mutations, URL validation
- XP transaction ledger and idempotent rewards
- Server-authoritative assessment timing/scoring
- Honest coding-challenge feedback semantics
- Real dashboard/analytics data and pagination of growing lists
- Account export/deletion/reset and roadmap lifecycle controls
- Health/security headers, local browser dependencies, and enforced baseline CSP
- PostgreSQL/Redis/WhiteNoise/Gunicorn preparation and production preflight

## Current quality phase

- [x] Replace stale architecture, schema, product, task, and UI documents
- [x] Validate scheduled challenge payloads before database writes
- [x] Add a cache-backed generation lock and scheduler-visible failures
- [x] Validate challenge submissions and hide internal errors
- [x] Make challenge attempt, XP, and streak updates transactional
- [x] Add direct Gemini structured-response and challenge-service tests
- [x] Make roadmap creation, code-review rewards, and generated-day writes atomic
- [x] Replace raw learning errors/prints and silent progress fallbacks
- [x] Validate note input/export filenames and generated practice problems
- [x] Add direct roadmap, analytics, seed-command, note, practice, and model tests
- [ ] Continue reviewing broad exception handlers at intentional API/provider boundaries
- [ ] Raise remaining low service coverage without testing implementation trivia

## Learning Intelligence feature branch

- [x] Define domain-agnostic V1 technical specification
- [x] Add Skill Pack, Skill, membership, and prerequisite schema
- [x] Add immutable LearningEvent and rebuildable SkillState schema
- [x] Add three starter domain packs plus shared foundations
- [x] Add cycle-validating idempotent Skill Pack seeder
- [x] Add deterministic mastery/confidence/freshness calculator
- [x] Add evidence write and state rebuild services/commands/tasks
- [x] Emit evidence from existing assessments, challenges, days, and reviews
- [x] Build routing and goal-specific diagnostics
- [x] Add onboarding and initial evidence-baseline pages
- [x] Build full Learning DNA profile, evidence explorer, and recommendation UI
- [ ] Build approval-based roadmap revisions
- [ ] Build tutor preferences and user-controlled memory

## Next frontend-security phase

- [x] Extract all page-specific inline CSS into versioned static stylesheets
- [x] Extract non-dynamic inline scripts and remove the first 23 event handlers
- [x] Add regression budgets so inline debt cannot increase
- [x] Extract the 10 remaining dynamic scripts and 34 event attributes
- [x] Remove inline-script allowances and block script attributes in enforced CSP
- [ ] Replace the remaining 201 template/runtime style attributes
- [ ] Remove `style-src-attr 'unsafe-inline'` after staging browser tests
- [ ] Add browser-level keyboard, responsive, and CSP smoke checks
- [ ] Verify YouTube embedding and external navigation under the stricter policy

## Background work phase

- [x] Configure Django's native Tasks contract and validated named queues
- [x] Add a scheduler-safe daily challenge task and enqueue command
- [x] Make production preflight reject development-only task backends
- [ ] Select/install a durable third-party backend and operate its worker
- [ ] Move slow lesson, assessment, image, and review AI calls to tracked jobs
- [ ] Add job timeout/retry policy, cancellation, and status UI
- [ ] Configure an actual external scheduler
- [ ] Test duplicate delivery and worker/provider outage behavior

## Private media phase

- [ ] Select private object storage
- [ ] Use non-public object keys and authenticated delivery
- [ ] Define retention/deletion policy for avatars and analyzed images
- [ ] Migrate a staging media copy and verify account deletion cleanup

## Staging phase

- [ ] Choose a provider and create isolated staging resources
- [ ] Provision PostgreSQL, Redis, transactional email, and secret management
- [ ] Restore sanitized backup data and run migrations
- [ ] Run production preflight, Gate A, readiness probes, and authorized smoke load
- [ ] Add error monitoring, metrics, logs, uptime checks, and alert ownership
- [ ] Practice rollback and database/media restoration

## Public-launch gate

Do not launch publicly until all strict preflight warnings are resolved or
explicitly accepted with documented controls. Required evidence includes:

- private media delivery
- background worker and scheduler
- CSP without legacy inline allowances
- working email/password reset
- monitoring and incident ownership
- restore-tested backups
- migration rollback decision point
- capacity/load results for the chosen infrastructure

## Definition of done for every bundle

1. Back up data before destructive or schema changes.
2. Keep `.env`, SQLite, media, and credentials out of Git.
3. Add focused regression tests.
4. Run `git diff --check` and the complete Gate A verifier.
5. Commit one coherent change and push it.
6. Confirm the remote commit and both CI matrix jobs before continuing.
