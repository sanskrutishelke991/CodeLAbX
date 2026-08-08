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
