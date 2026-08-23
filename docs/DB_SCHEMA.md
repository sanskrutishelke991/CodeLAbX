# CodeLabX data model

Last reviewed: 2026-08-08

This document is a relationship map, not a substitute for migrations. The source
of truth is each app's `models.py` plus committed migration files.

## Database modes

- Development default: SQLite at `SQLITE_PATH`.
- Staging/production preparation: PostgreSQL through a validated `DATABASE_URL`.
- No production database migration has been performed yet.

## Identity and profile

### Django `auth.User`

Built-in account identity and password hashing. Registration additionally
requires a unique normalized email at the application layer.

### `accounts.UserProfile`

One-to-one with `User`. Stores biography, avatar, location, learning preferences,
and public/private profile visibility. Avatar media is deleted during confirmed
account deletion.

### `accounts.EmailPreference`

Optional one-to-one account preference for explicit weekly-report opt-in, send
day, and included report sections. It does not exist merely because a settings page
was opened. Enabling delivery requires a valid account email.

### `accounts.WeeklyReportDelivery`

Owner-scoped idempotency ledger for scheduled seven-day report periods. It stores
status, attempts, timestamps, subject, and a content hash—not the report body or
provider secrets. The unique user/period constraint prevents duplicate scheduled
email for the same week; explicit previews do not create ledger rows.

## Learning

### `learning.Roadmap`

Owned by one user. Stores ML or DSA track, title, level, duration, daily hours,
dates, and lifecycle status (`active`, `paused`, `completed`, `archived`).

### `learning.Day`

Belongs to a roadmap. Stores ordered daily curriculum, completion state, and
optional sanitized/generated lesson content. `(roadmap, day_number)` is unique.
Deleting a roadmap cascades to its days.

## Assessments

### `assessments.Test`

Owned generated assessment containing validated question objects, authoritative
answer keys, timing configuration, score, and lifecycle status. Answer keys are
removed before question data reaches the browser.

### `assessments.TestAttempt`

Links one user and test attempt. Stores server-controlled deadline, submitted
answers, score, completion timestamp, and finalization state. Finalized attempts
cannot replay XP.

## Challenges

### `challenges.Challenge`

Global challenge for one date and type (`coding` or `theory`). The pair
`(date, challenge_type)` is unique. Structured provider payloads are validated
before storage.

### `challenges.UserChallenge`

Owner-scoped attempt with a unique `(user, challenge)` pair. Stores selected
option or submitted code, AI feedback metadata, completion, and actually awarded
XP. Coding feedback is not verified correctness.

### `challenges.ChallengeStreak`

One-to-one user summary. Tracks consecutive challenge days, longest streak, last
challenge date, and total unique completed challenges.

## AI tools

### `ai_tools.ChatSession` and `ai_tools.ChatMessage`

A session belongs to one user; messages belong to one session. History endpoints
scope every lookup to the owner. Assistant Markdown is sanitized again when
rendered.

### `ai_tools.ImageAnalysis`

Owner-scoped record for a normalized upload, question/type, generated analysis,
status, and XP state. Failed analysis removes its database record and stored
file.

## Content

### `content.VideoCategory` and `content.Video`

Curated video metadata. Videos belong to categories and carry difficulty,
feature, active, and view metadata.

### `content.UserVideoProgress`

Unique per `(user, video)`. Stores watched/favorite state and timestamps. The XP
ledger prevents repeat watched rewards.

## Practice

### `practice.CodeReview`

Owner-scoped submitted code, language/problem context, sanitized AI feedback,
and timestamp. It records review output, not executed test results.

## Notes

### `notes.Note`

Private user note with title, content, topic, tags, and timestamps.

### `notes.Bookmark`

Private user bookmark. URLs are restricted to approved schemes or local paths.

## Progress and integrity

### `progress.XPTransaction`

Append-only reward ledger. Each user/idempotency-key pair represents one logical
reward event and prevents replay across retries.

### `progress.UserLevel`

One-to-one user summary for level, current XP, and total earned XP.

### `progress.DailyActivity`

Unique daily user activity summary for recorded study minutes and completed
learning actions.

### `progress.UserStreak`

One-to-one general learning streak summary.

### `progress.Badge` and `progress.UserBadge`

Badge definition plus unique earned user/badge relation.

## Learning Intelligence

### `intelligence.SkillPack`, `Skill`, and `SkillPackMembership`

Versioned reviewed curriculum packs reference globally canonical skills, allowing
shared foundations to appear in Programming/DSA, ML, and Django paths without
duplicating skill identity.

### `intelligence.SkillPrerequisite`

Directed prerequisite edge with bounded mastery/confidence thresholds. The Skill
Pack validator rejects unknown skills, self-dependencies, duplicates, and cycles
before database writes.

### `intelligence.LearningEvent`

Immutable, owner-scoped evidence event with a per-user idempotency key, bounded
numeric outcome/difficulty/weight, hints/retries/duration, source identity,
algorithm schema version, and small JSON metadata object.

### `intelligence.SkillState`

Rebuildable `(user, skill)` snapshot containing deterministic mastery,
confidence, freshness, evidence count/weight, latest evidence, misconception
codes, and algorithm version. It is derived from LearningEvent and is not an AI
opinion or XP score.

### `intelligence.LearnerIntelligenceProfile`

Owner one-to-one goal and selected Skill Pack plus routing/goal diagnostic
completion timestamps. Intelligence data remains private by default.

### `intelligence.DiagnosticAttempt` and `DiagnosticResponse`

Owner-scoped authoritative attempt records for versioned curated question sets.
Responses reference canonical skills; answer keys remain only in reviewed server
JSON definitions and are never included in browser question objects.

### `intelligence.Mission`

Owner-scoped, explainable next-step proposal tied to a primary skill and optional
supporting skills. It stores a deterministic recommendation key, bounded rationale
and success-criteria objects, expected time, evidence-policy version, and lifecycle
status. Recalculating an unchanged evidence snapshot is idempotent; a changed
snapshot expires the superseded proposal. Retention missions use a separate
freshness-review key and cannot displace an undecided or active mission. A proposal
does not mutate a roadmap.

### `intelligence.RoadmapRevision` and `RoadmapNode`

Versioned adaptive skill-route sidecars attached to an owned `learning.Roadmap`.
A roadmap has at most one active and one proposed revision. Nodes store ordered
skills, prerequisite readiness, optional mission association, expected time, and
a learner-controlled position pin. Accept/reject/postpone decisions are recorded;
restoration copies a superseded snapshot into a new revision instead of rewriting
history. These tables never replace or mutate legacy `learning.Day` rows.

### `intelligence.TutorPreference`

One-to-one explicit teaching choices for explanation depth, tutor mode, code
density, answer language, pace, study-block length, bounded accessibility flags,
explicit learning-record context permission, and opt-in feedback adaptation.
Opening AI chat never creates this profile silently.

### `intelligence.TutorMemory`

Owner-scoped, bounded, visible context with category, content, storage reason,
source, active/paused state, and learner-confirmation state. Session summaries
reference an owned chat session and are deleted with that session. Likely
credentials and secret assignments are rejected. Learners can edit, pause, delete,
or permanently forget every item.

### `intelligence.TutorFeedback`

One owner-scoped feedback choice per assistant message. Repeated signals can create
one visible, editable memory suggestion only when observed adaptation is explicitly
enabled. Feedback and suggestions are not skill evidence or model fine-tuning.

## Deletion and privacy behavior

Most user-owned records cascade from `User`. Account deletion additionally
removes owned media after confirmation. JSON account export provides a bounded
copy of current user data. Leaderboards include public profiles plus the current
user only.

## Backup and migration rule

Before schema or backend changes, create and verify an external database dump,
media archive, and restore test. Review `python manage.py migrate --plan` before
applying migrations. Repository-local SQLite/media files are never a production
backup.
