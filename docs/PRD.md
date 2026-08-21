# CodeLabX product requirements

Last reviewed: 2026-08-08

## Product purpose

CodeLabX is a development-stage learning platform for structured ML and DSA
roadmaps, recorded practice, assessments, challenges, notes, video progress, and
optional AI-assisted explanations. It must show real stored learner activity and
must distinguish AI feedback from verified results.

## Intended users

- Learners building consistent study habits
- Beginners through advanced learners selecting an explicit roadmap level
- Developers who want explanatory, non-executing code feedback
- Project administrators curating videos, badges, and operational data

## Current functional scope

### Accounts

- Username/password registration with unique normalized email
- Login/register throttling and POST-only logout
- Profile visibility, editing, password reset, JSON export, and confirmed deletion

### Learning

- Rule-based Machine Learning and Data Structures & Algorithms roadmaps
- User-selected duration, daily hours, level, and optional start date
- Pause, resume, archive, and delete lifecycle actions
- Daily completion with idempotent activity and XP
- Optional AI-generated lesson explanation

### Assessment and practice

- Validated generated MCQ assessments
- Answer keys retained server-side
- Server-controlled deadlines and authoritative finalization
- Practice-problem generation with bounded input/output validation
- Sanitized AI code review clearly labeled as non-executing feedback

### Challenges

- One global coding and theory challenge per date
- Scheduler-oriented management command, not AI work during page GET
- Deterministic theory scoring
- Coding attempt credit plus optional AI feedback; never verified correctness
- Idempotent rewards and owner-scoped history

### Progress and content

- XP transaction ledger, levels, streaks, badges, and public-profile leaderboard
- 365-day activity view and stored analytics
- Paginated video library, watched/favorite state, notes, bookmarks, chats, images,
  roadmaps, and assessments

## Product truth requirements

- Do not claim learner counts, ratings, availability, speed, pricing guarantees,
  encryption, mobile apps, or support channels without evidence.
- Demo/interface values must be labeled illustrative.
- AI output may be incomplete or incorrect and must not be called authoritative.
- Code feedback does not execute submitted code.
- Analytics must derive from owner-scoped stored records.
- Disabled/unconfigured features must fail closed with clear generic messages.

## Security and privacy requirements

- No committed secrets, databases, or media
- CSRF protection and POST for state changes
- Owner filtering on private objects
- Bounded JSON and image uploads
- Decoded/normalized images with metadata removed
- Allowlisted AI HTML sanitizer
- Shared production throttling through Redis
- Idempotency keys for rewards
- Generic public provider/internal errors
- Account export and deletion controls

## Non-goals for the current stage

- Public production launch
- Native mobile application
- Social login or public API
- Microservices
- Executing untrusted learner code
- Guaranteed AI correctness or 24/7 availability
- Billing or a permanent pricing promise

## Operational acceptance gates

A change is complete only when focused tests and `scripts/verify.py` pass. The
native Django Tasks contract may execute immediately during development; this is
not an asynchronous production worker. Public production additionally requires
PostgreSQL/Redis staging, a durable task backend/worker, private object
storage, asynchronous AI jobs, real email, monitoring, final CSP without legacy
style attributes, backup restoration, rollback rehearsal, and authorized
load testing.

## Success measures

Use measurable internal signals rather than marketing claims:

- Gate A remains green on Python 3.12 and 3.14
- Reward replay tests remain idempotent
- Private object authorization tests remain green
- Generated structured content is rejected when malformed
- Query budgets do not regress
- Readiness fails when required dependencies fail
- Staging restore, rollback, and smoke checks are recorded before launch
