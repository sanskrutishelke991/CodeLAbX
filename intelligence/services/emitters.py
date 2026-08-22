"""Non-blocking evidence emitters for existing CodeLabX workflows."""

from __future__ import annotations

import logging
from decimal import Decimal
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction

from intelligence.models import Skill
from intelligence.services.evidence import record_learning_event

logger = logging.getLogger(__name__)

KEYWORD_SKILLS = [
    (("csrf", "session", "cookie"), "django.csrf_sessions"),
    (("permission", "owner", "authorization"), "django.authorization"),
    (("authentication", "login", "password"), "django.authentication"),
    (("migration",), "django.migrations"),
    (("orm", "model", "queryset"), "django.orm"),
    (("api", "json", "endpoint"), "django.json_apis"),
    (("graph", "bfs", "dfs"), "dsa.graphs"),
    (("dynamic programming", "memoization"), "dsa.greedy_dynamic"),
    (("recursion", "recursive"), "dsa.recursion"),
    (("array", "string", "two pointer", "sliding window"), "dsa.arrays_strings"),
    (("complexity", "big o"), "dsa.complexity"),
    (("classification",), "ml.classification"),
    (("regression",), "ml.regression"),
    (("metric", "evaluation", "precision", "recall"), "ml.model_evaluation"),
    (("overfit", "generalization"), "ml.generalization"),
    (("pandas", "dataframe"), "ml.pandas"),
    (("debug", "bug", "error"), "programming.debugging"),
    (("function", "return", "parameter"), "python.functions"),
    (("class", "object", "inheritance"), "python.oop"),
    (("dictionary", "list", "tuple", "set"), "python.collections"),
]


def infer_skill_code(*, text="", topic="", fallback="programming.problem_decomposition"):
    haystack = f"{topic} {text}".casefold()
    for keywords, skill_code in KEYWORD_SKILLS:
        if any(keyword in haystack for keyword in keywords):
            return skill_code
    if "ml" in haystack or "machine learning" in haystack:
        return "ml.data_splitting"
    if "django" in haystack or "web" in haystack:
        return "django.routing_views"
    if "dsa" in haystack or "algorithm" in haystack:
        return "dsa.arrays_strings"
    if "python" in haystack:
        return "python.syntax_types"
    return fallback


def _safe_record(**kwargs):
    try:
        record_learning_event(**kwargs)
    except (Skill.DoesNotExist, ValidationError):
        logger.warning(
            "Learning evidence was skipped because its skill/data was unavailable",
            exc_info=True,
        )
    except Exception:
        logger.exception("Learning evidence emission failed")


def _enqueue_after_commit(**kwargs):
    transaction.on_commit(partial(_safe_record, **kwargs))


def emit_day_completion(user, day):
    skill_code = infer_skill_code(
        topic=day.roadmap.topic,
        text=f"{day.title} {day.description}",
    )
    _enqueue_after_commit(
        user=user,
        skill_code=skill_code,
        event_type="lesson_complete",
        source_type="day",
        source_id=str(day.id),
        idempotency_key=f"intelligence:day:{day.id}",
        outcome=None,
        difficulty=Decimal("0.3000"),
        evidence_weight=Decimal("0.200"),
        duration_seconds=int(float(day.estimated_hours) * 3600),
        metadata={"roadmap_id": day.roadmap_id},
    )


def emit_challenge_attempt(user, attempt):
    challenge = attempt.challenge
    is_theory = challenge.challenge_type == "theory"
    skill_code = infer_skill_code(
        text=f"{challenge.title} {challenge.description}",
        topic=challenge.challenge_type,
    )
    _enqueue_after_commit(
        user=user,
        skill_code=skill_code,
        event_type="challenge_answer" if is_theory else "coding_attempt",
        source_type="challenge",
        source_id=str(attempt.id),
        idempotency_key=f"intelligence:challenge-attempt:{attempt.id}",
        outcome=(Decimal("1") if attempt.is_correct else Decimal("0"))
        if is_theory
        else None,
        difficulty={
            "easy": Decimal("0.3000"),
            "medium": Decimal("0.6000"),
            "hard": Decimal("0.9000"),
        }.get(challenge.difficulty, Decimal("0.5000")),
        evidence_weight=Decimal("0.900") if is_theory else Decimal("0.250"),
        duration_seconds=attempt.time_taken_seconds,
        metadata={"evaluation_type": attempt.evaluation_type},
    )


def emit_code_review(user, review, *, language, problem=""):
    skill_code = infer_skill_code(
        text=problem,
        topic=language,
        fallback="programming.debugging",
    )
    _enqueue_after_commit(
        user=user,
        skill_code=skill_code,
        event_type="ai_review",
        source_type="code_review",
        source_id=str(review.id),
        idempotency_key=f"intelligence:code-review:{review.id}",
        outcome=None,
        difficulty=Decimal("0.5000"),
        evidence_weight=Decimal("0.150"),
        metadata={"language": language},
    )


def emit_assessment_attempt(user, test, attempt):
    answers = attempt.answers if isinstance(attempt.answers, dict) else {}
    for index, question in enumerate(test.questions):
        if not isinstance(question, dict):
            continue
        correct = question.get("correct")
        selected = answers.get(str(index), answers.get(index))
        if not isinstance(correct, int) or isinstance(correct, bool):
            continue
        explicit_skill = question.get("skill_code")
        if isinstance(explicit_skill, str) and explicit_skill:
            skill_code = explicit_skill
        else:
            skill_code = infer_skill_code(
                text=str(question.get("question", "")),
                topic=test.topic,
            )
        _enqueue_after_commit(
            user=user,
            skill_code=skill_code,
            event_type="assessment_answer",
            source_type="assessment",
            source_id=f"{attempt.id}:{index}",
            idempotency_key=f"intelligence:assessment:{attempt.id}:{index}",
            outcome=Decimal("1") if selected == correct else Decimal("0"),
            difficulty={
                "easy": Decimal("0.3000"),
                "medium": Decimal("0.6000"),
                "hard": Decimal("0.9000"),
            }.get(test.difficulty, Decimal("0.5000")),
            evidence_weight=Decimal("1.000"),
            duration_seconds=attempt.time_taken_seconds,
            metadata={"test_id": test.id, "question_index": index},
        )
