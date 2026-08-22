# CodeLabX Learning Intelligence V1 — technical specification

Planning date: 2026-08-22
Stable code baseline: `7f267f2`
Target feature branch: `feature/learning-intelligence-v1`

## 1. V1 outcome

V1 must prove this statement:

> Two college learners with the same goal but different evidence receive different,
> explainable next missions and can approve or reject the proposed roadmap change.

V1 is not a universal knowledge graph, psychological profile, or fully verified
credential system. It is a transparent adaptive-learning foundation that supports
three starter domains and can add more through versioned Skill Packs.

## 2. Confirmed decisions and working defaults

### Confirmed

- Primary learner: college CS student
- Skill domains: Programming/DSA, Machine Learning, Django/full-stack
- Adaptation: proposed by the engine, applied only after learner approval
- Tutor: explicit onboarding choice followed by feedback-based adaptation
- Minors may use the system: privacy and community default to restricted

### Working defaults, adjustable later

- Onboarding goal is learner-selected; placement preparation is highlighted, not
  silently selected.
- Skill Passport V1 says “evidence observed,” not “verified skill.”
- No direct messages in community V1; groups are private/invite-only.
- UI language starts in English. Django i18n is added before Hindi/other catalogs.
- Existing AI daily limit remains the initial budget ceiling; intelligence
  calculations themselves do not call AI.
- No untrusted code execution in V1.

## 3. Architecture

Add one Django app inside the existing monolith:

```text
intelligence/
  admin.py
  apps.py
  models.py
  services/
    evidence.py
    mastery.py
    recommendations.py
    roadmap.py
    tutor_context.py
  management/commands/
    seed_skill_packs.py
    rebuild_skill_states.py
  skill_packs/
    shared.json
    programming_dsa.json
    machine_learning.json
    django_fullstack.json
  tests/
```

Do not create a microservice. Intelligence services consume existing learning,
assessment, challenge, practice, and progress records through explicit event
emitters.

## 4. Domain model

### 4.1 `SkillPack`

Purpose: versioned curriculum package.

Fields:

- `code`: unique stable code, e.g. `programming_dsa`
- `name`
- `description`
- `version`: positive integer
- `is_active`
- `created_at`, `updated_at`

Constraint: unique `(code, version)` if historical versions are retained. V1 may
use a unique active code plus integer version updated by seed command.

### 4.2 `Skill`

Purpose: canonical skill shared between packs.

Fields:

- `code`: globally unique, immutable identifier
- `name`
- `description`
- `domain`
- `difficulty_band`: 1–5
- `default_half_life_days`
- `is_active`
- timestamps

Examples:

- `programming.problem_decomposition`
- `programming.debugging`
- `python.functions`
- `dsa.arrays`
- `ml.model_evaluation`
- `django.orm`

### 4.3 `SkillPackMembership`

Purpose: connect reusable skills to packs.

Fields:

- pack
- skill
- order
- `is_core`
- `is_required`

Constraint: unique `(pack, skill)`.

### 4.4 `SkillPrerequisite`

Fields:

- prerequisite skill
- dependent skill
- minimum mastery threshold
- minimum confidence threshold
- strength/importance

Constraints:

- unique `(prerequisite, dependent)`
- prerequisite cannot equal dependent
- cycle detection in seed validation/service

### 4.5 `LearningEvent`

Immutable evidence ledger. Never update an event after creation except through an
explicit corrective event.

Fields:

- user
- skill
- `event_type`
- `source_type`
- `source_id`
- `idempotency_key`
- `outcome`: decimal 0–1, nullable when event is not scoreable
- `difficulty`: decimal 0–1
- `evidence_weight`
- `hints_used`
- `retry_count`
- `duration_seconds`
- bounded JSON metadata
- `occurred_at`
- `schema_version`
- `created_at`

Constraint: unique `(user, idempotency_key)`.

Indexes:

- `(user, skill, occurred_at)`
- `(user, event_type, occurred_at)`
- `(source_type, source_id)`

### 4.6 `SkillState`

Current derived snapshot per user/skill.

Fields:

- user
- skill
- `mastery`: 0–1
- `confidence`: 0–1
- `freshness`: 0–1
- `evidence_count`
- `total_evidence_weight`
- `last_evidence_at`
- bounded misconception-code list
- `algorithm_version`
- `calculated_at`

Constraint: unique `(user, skill)`.

This table is derived and can be rebuilt from `LearningEvent`.

### 4.7 `Mission`

Fields:

- user
- primary skill
- additional skills (many-to-many)
- type: `diagnostic`, `learn`, `practice`, `remediation`, `retention`,
  `project`, `stretch`
- status: `proposed`, `accepted`, `active`, `completed`, `skipped`, `expired`
- title and description
- deterministic rationale JSON
- success criteria JSON
- expected minutes
- evidence policy/version
- timestamps

### 4.8 `RoadmapRevision`

Sidecar to the existing `learning.Roadmap`; legacy roadmaps remain valid.

Fields:

- roadmap
- revision number
- status: `proposed`, `active`, `rejected`, `superseded`
- reason code
- summary
- input state version/timestamp
- algorithm version
- created/decided timestamps

Constraint: unique `(roadmap, revision_number)`.

### 4.9 `RoadmapNode`

Fields:

- revision
- skill
- mission, nullable
- order
- status: `locked`, `ready`, `active`, `complete`, `skipped`
- rationale
- expected minutes
- `is_user_locked`

Constraint: unique `(revision, order)`.

### 4.10 `TutorPreference`

One-to-one with user.

Fields:

- explanation depth: concise/balanced/detailed
- teaching mode: direct/example-first/socratic/mixed
- code density: low/medium/high
- preferred language
- pace
- session minutes
- accessibility preferences JSON
- whether observed adaptation is allowed
- timestamps

### 4.11 `TutorMemory`

Fields:

- user
- category: goal, misconception, preference, project, revisit
- bounded text
- reason it was stored
- source event/session ID
- active flag
- timestamps

Rules:

- visible/editable/deletable by user
- no credentials, secrets, private repository content, hidden emotional profile,
  or unrestricted raw transcripts
- “forget all” operation

## 5. Skill Pack format

Skill Packs are reviewed JSON fixtures loaded by an idempotent management command.
They are version-controlled, testable, and independent of AI output.

Example:

```json
{
  "code": "programming_dsa",
  "name": "Programming and DSA",
  "version": 1,
  "skills": [
    {
      "code": "programming.problem_decomposition",
      "name": "Problem Decomposition",
      "difficulty_band": 1,
      "half_life_days": 45,
      "order": 10,
      "required": true,
      "prerequisites": []
    }
  ]
}
```

Seed validation rejects:

- duplicate codes/order
- unknown prerequisites
- cycles
- invalid thresholds
- unsupported domains
- missing descriptions

## 6. Starter Skill Packs

### 6.1 Shared core

- computational thinking
- problem decomposition
- debugging
- reading errors
- testing fundamentals
- Git fundamentals
- command-line fundamentals
- SQL fundamentals
- project planning

### 6.2 Programming + DSA pack

- Python syntax and types
- control flow
- functions
- collections
- OOP
- exceptions
- files/modules
- complexity analysis
- arrays/strings
- linked lists
- stacks/queues
- hash maps
- trees/heaps
- graphs
- recursion
- sorting/searching
- greedy algorithms
- dynamic programming

### 6.3 Machine Learning pack

- Python/data prerequisites
- NumPy
- Pandas
- data cleaning
- visualization
- descriptive statistics
- probability basics
- linear algebra basics
- train/validation/test split
- regression
- classification
- clustering
- feature engineering
- model metrics
- overfitting/generalization
- cross-validation
- ensembles
- neural-network foundations
- responsible ML
- reproducible experiments

### 6.4 Django/full-stack pack

- HTTP/request-response
- HTML/CSS/JavaScript foundations
- Django project/app structure
- URL routing
- templates
- forms/validation
- ORM/modeling
- migrations
- authentication
- authorization/object ownership
- sessions/CSRF
- file uploads
- JSON APIs
- query optimization
- automated testing
- security headers/CSP
- logging/configuration
- deployment concepts

## 7. Event mapping V1

| Existing interaction | Event type | Initial weight | Notes |
| --- | --- | ---: | --- |
| Correct deterministic assessment answer | `assessment_answer` | 1.0 | medium/high-quality evidence |
| Incorrect assessment answer | `assessment_answer` | 1.0 | updates gap, not punishment |
| Correct theory challenge | `challenge_answer` | 0.9 | deterministic |
| Coding challenge attempt | `coding_attempt` | 0.25 | not correctness verified |
| AI code review | `ai_review` | 0.15 | weak observed evidence only |
| Completed roadmap day | `lesson_complete` | 0.20 | participation evidence |
| Diagnostic answer | `diagnostic_answer` | 1.1 | curated deterministic question |
| Project rubric item | `project_rubric` | 1.2 | later wave |
| Tutor teach-back rubric | `teach_back` | 0.35 | supporting evidence |
| Self rating | `self_report` | 0.05 | never verification |

Hint/retry modifiers reduce confidence in one event but never produce negative XP or
shaming language.

## 8. Mastery engine V1

The first algorithm is deterministic and versioned as `weighted-evidence-v1`.

For scoreable event `i`:

```text
adjusted_weight_i =
    evidence_weight
  × difficulty_factor
  × hint_factor
  × duplicate_dampening

mastery =
  (prior_weight × 0.50 + Σ adjusted_weight_i × outcome_i)
  / (prior_weight + Σ adjusted_weight_i)

confidence = 1 - exp(-Σ adjusted_weight_i / 5)

freshness = exp(-days_since_strong_evidence / half_life_days)
```

Initial constants live in code/settings and are covered by boundary tests.

Rules:

- mastery remains between 0 and 1
- confidence remains between 0 and 1
- freshness remains between 0 and 1
- events with null outcome affect engagement/freshness only when policy allows
- duplicate/replayed source events are rejected by idempotency key
- recomputation from the ledger must reproduce the same state
- no Gemini call participates in numeric calculation

## 9. Recommendation engine V1

Candidate skill must satisfy prerequisite policy. Score:

```text
priority =
  goal_relevance
  × max(target_mastery - mastery, minimum_gap)
  × prerequisite_readiness
  × (1 + review_due_bonus)
  × evidence_need
  × preference_effectiveness
  - repetition_penalty
```

Output rationale JSON:

```json
{
  "reason_codes": ["SKILL_GAP", "PREREQUISITE", "LOW_CONFIDENCE"],
  "evidence_count": 7,
  "mastery": 0.61,
  "confidence": 0.68,
  "freshness": 0.93,
  "expected_minutes": 35,
  "alternatives": ["python.functions", "programming.debugging"]
}
```

AI may turn this into friendly wording, but it cannot invent numbers/reason codes
or select an ineligible skill.

## 10. Approval-based roadmap flow

1. Engine creates a proposed `Mission` and `RoadmapRevision`.
2. UI displays old/new node diff, rationale, expected time, and alternatives.
3. Learner accepts, rejects, or postpones.
4. Accept transaction supersedes old active revision and activates new revision.
5. Rejection is stored to avoid repeatedly proposing the same change.
6. User-locked nodes cannot be removed automatically.
7. Every revision is reversible.

## 11. Diagnostic flow

### Routing diagnostic

Nine to twelve curated questions covering shared programming, data/ML, and web
foundations. Purpose: route depth, not label intelligence.

### Goal selection

- semester/course support
- placement/interview preparation
- project building
- machine learning
- full-stack development
- custom goal

### Goal-specific diagnostic

Ten to fifteen curated questions/tasks from the selected Skill Pack.

Diagnostic answer keys remain server-side. Each answer emits an idempotent event.
Learners may skip diagnostics and start with low-confidence priors.

## 12. Learning DNA API/UI

### Service result

```json
{
  "algorithm_version": "weighted-evidence-v1",
  "calculated_at": "...",
  "skills": [
    {
      "code": "programming.problem_decomposition",
      "mastery": 0.61,
      "confidence": 0.68,
      "freshness": 0.93,
      "evidence_count": 7,
      "last_evidence_at": "..."
    }
  ],
  "current_bottleneck": {},
  "recommended_mission": {}
}
```

### Profile display

Each bar shows mastery, confidence, freshness, evidence count, and details link.
Do not render a score without confidence/evidence.

### Privacy

- private by default
- not included in leaderboard
- export/delete with account
- public passport is a separate opt-in later

## 13. Tutor personalization contract

### Context builder input

- accepted mission
- current relevant SkillStates
- explicit TutorPreference
- active bounded TutorMemory
- latest compact session summary
- trusted curriculum excerpts
- current user request

### Hard limits

- maximum memory items and characters
- source labels
- sanitize retrieved content
- user content cannot override system policy
- no hidden memory writes
- no automatic memory from sensitive content

### Response feedback events

- helped
- too_fast
- too_detailed
- more_examples
- more_code
- ask_me_questions
- already_known

Observed preference changes require repeated evidence or explicit confirmation.

## 14. API/routes V1

```text
GET/POST  /intelligence/onboarding/
GET       /intelligence/diagnostic/
POST      /intelligence/diagnostic/submit/
GET       /intelligence/dna/
POST      /intelligence/recommendations/recalculate/
POST      /intelligence/recommendations/<id>/accept/
POST      /intelligence/recommendations/<id>/reject/
GET/POST  /intelligence/tutor/preferences/
GET       /intelligence/tutor/memory/
POST      /intelligence/tutor/memory/<id>/update/
POST      /intelligence/tutor/memory/<id>/delete/
POST      /intelligence/tutor/memory/forget-all/
```

All state changes are authenticated, owner-scoped, POST, CSRF-protected, bounded,
and rate-limited where AI is involved.

## 15. Integration strategy

### Existing roadmap compatibility

- existing Roadmap/Day tables remain
- intelligence revisions are a sidecar
- legacy roadmap renders when no active revision exists
- no destructive data migration in Sprint 1

### Emitters

Use service calls after successful transaction commit:

```text
assessment finalization -> assessment evidence events
challenge finalization  -> challenge evidence event
roadmap-day completion   -> participation event
code review completion   -> low-weight observed event
```

Use deterministic idempotency keys based on source object and event type.

### Tasks

- state recomputation may use the native task contract
- local backend executes immediately
- production requires a durable backend/worker
- request correctness must not depend on the task completing instantly

## 16. Admin and operations

Admin interfaces:

- skill packs/skills/prerequisites
- read-only learning-event evidence
- skill-state snapshots
- missions/recommendations/revisions
- tutor memories with strict access and no secret fields

Management commands:

```text
python manage.py seed_skill_packs
python manage.py seed_skill_packs --check
python manage.py rebuild_skill_states --user <id>
python manage.py rebuild_skill_states --all --enqueue
```

Operational metrics later:

- events emitted/rejected as duplicate
- state recomputation failures
- recommendation acceptance/rejection
- stale-state age
- AI context/token cost

## 17. Minor-safe defaults

- Learning DNA and roadmap private by default
- no public profile or sharing during intelligence MVP
- no direct messaging
- future groups invite-only by default
- report/block/moderation before comments/forum launch
- avoid comparative intelligence labels
- no manipulative companion language or dependency encouragement
- clear disclosure that tutor is AI
- bounded memory with delete/forget controls

Legal policy and age handling require review before public community launch.

## 18. Sprint plan

### Sprint 1 — Intelligence foundation

Deliver:

- `intelligence` app
- Skill Pack/Skill/prerequisite models
- LearningEvent and SkillState models
- migrations/admin
- idempotent Skill Pack seeder with cycle validation
- deterministic mastery/confidence/freshness service
- direct tests and Gate A

No UI and no existing event emitters yet.

### Sprint 2 — Evidence integration and diagnostics

Deliver:

- event emission service
- assessment/challenge/day/review emitters using `transaction.on_commit`
- routing + three goal diagnostics
- diagnostic UI and authoritative submission
- state rebuild command/task

### Sprint 3 — Learning DNA and recommendations

Deliver:

- DNA profile panel
- evidence explanation view
- bottleneck selection
- Mission and recommendation engine
- “why this mission?” card

### Sprint 4 — Adaptive roadmap revisions

Deliver:

- RoadmapRevision/RoadmapNode
- proposed diff UI
- accept/reject/postpone/restore
- compatibility with legacy roadmap days

### Sprint 5 — Tutor personalization

Deliver:

- preference onboarding
- TutorPreference/TutorMemory
- memory dashboard and forget-all
- context builder and tutor modes
- feedback events

## 19. Sprint 1 acceptance criteria

1. Skill Packs load idempotently and reject malformed/cyclic data.
2. Shared skills can belong to multiple packs without duplication.
3. LearningEvent is immutable and idempotent.
4. Rebuilding SkillState from identical events is deterministic.
5. Mastery/confidence/freshness stay in valid ranges.
6. Freshness changes with time without silently rewriting historical evidence.
7. No Gemini call is used for numeric skill calculation.
8. Admin registrations and owner scoping are tested.
9. No existing roadmap/account data is reset.
10. Full Gate A remains green.

## 20. Explicitly out of Sprint 1

- public sharing
- Skill Passport/certificates
- GitHub OAuth
- social/community
- PWA/TTS/voice
- translated catalogs
- real production task worker
- isolated code execution

These remain planned waves and should not dilute the Learning Intelligence
foundation.
