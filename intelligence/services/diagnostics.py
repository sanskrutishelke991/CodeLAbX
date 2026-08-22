"""Authoritative curated diagnostic loading and submission."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from intelligence.models import (
    DiagnosticAttempt,
    DiagnosticResponse,
    LearnerIntelligenceProfile,
    Skill,
)
from intelligence.services.evidence import record_learning_event
from intelligence.services.mastery import rebuild_skill_state

DIAGNOSTIC_DIRECTORY = Path(__file__).resolve().parent.parent / "diagnostics"


@dataclass(frozen=True)
class DiagnosticDefinition:
    code: str
    version: int
    title: str
    questions: list[dict]

    @property
    def public_questions(self):
        return [
            {
                "id": question["id"],
                "skill": question["skill"],
                "prompt": question["prompt"],
                "options": question["options"],
            }
            for question in self.questions
        ]


def _diagnostic_path(stage: str, profile: LearnerIntelligenceProfile) -> Path:
    if stage == "routing":
        return DIAGNOSTIC_DIRECTORY / "routing.json"
    if stage == "goal":
        return DIAGNOSTIC_DIRECTORY / f"{profile.selected_pack.code}.json"
    raise ValidationError("Unsupported diagnostic stage.")


def load_diagnostic(
    stage: str,
    profile: LearnerIntelligenceProfile,
) -> DiagnosticDefinition:
    path = _diagnostic_path(stage, profile)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("The diagnostic definition is unavailable.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("The diagnostic definition is invalid.")
    code = payload.get("code")
    title = payload.get("title")
    version = payload.get("version")
    questions = payload.get("questions")
    if (
        not isinstance(code, str)
        or not isinstance(title, str)
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(questions, list)
        or not questions
        or len(questions) > 30
    ):
        raise ValidationError("The diagnostic definition is invalid.")

    question_ids = set()
    validated = []
    for question in questions:
        if not isinstance(question, dict):
            raise ValidationError("A diagnostic question is invalid.")
        question_id = question.get("id")
        skill_code = question.get("skill")
        prompt = question.get("prompt")
        options = question.get("options")
        correct = question.get("correct")
        difficulty = question.get("difficulty", 0.5)
        if (
            not isinstance(question_id, str)
            or not question_id
            or len(question_id) > 100
            or question_id in question_ids
            or not isinstance(skill_code, str)
            or not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt) > 1000
            or not isinstance(options, list)
            or len(options) != 4
            or any(
                not isinstance(option, str)
                or not option.strip()
                or len(option) > 500
                for option in options
            )
            or isinstance(correct, bool)
            or not isinstance(correct, int)
            or not 0 <= correct < len(options)
        ):
            raise ValidationError("A diagnostic question is invalid.")
        try:
            normalized_difficulty = Decimal(str(difficulty))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("Question difficulty is invalid.") from exc
        if not Decimal("0") <= normalized_difficulty <= Decimal("1"):
            raise ValidationError("Question difficulty is invalid.")
        question_ids.add(question_id)
        validated.append(
            {
                "id": question_id,
                "skill": skill_code,
                "prompt": prompt.strip(),
                "options": [option.strip() for option in options],
                "correct": correct,
                "difficulty": normalized_difficulty,
            }
        )

    known_skills = set(
        Skill.objects.filter(
            code__in={item["skill"] for item in validated},
            is_active=True,
        ).values_list("code", flat=True)
    )
    missing = {item["skill"] for item in validated} - known_skills
    if missing:
        raise ValidationError(
            f"Diagnostic references unseeded skills: {', '.join(sorted(missing))}."
        )
    return DiagnosticDefinition(code, version, title, validated)


def next_diagnostic_stage(profile: LearnerIntelligenceProfile) -> str | None:
    if profile.routing_diagnostic_completed_at is None:
        return "routing"
    if profile.goal_diagnostic_completed_at is None:
        return "goal"
    return None


@transaction.atomic
def get_or_create_current_attempt(user, profile):
    stage = next_diagnostic_stage(profile)
    if stage is None:
        return None, None
    definition = load_diagnostic(stage, profile)
    attempt = (
        DiagnosticAttempt.objects.select_for_update()
        .filter(
            user=user,
            stage=stage,
            diagnostic_code=definition.code,
            question_set_version=definition.version,
            status="started",
        )
        .first()
    )
    if attempt is None:
        attempt = DiagnosticAttempt.objects.create(
            user=user,
            pack=profile.selected_pack if stage == "goal" else None,
            stage=stage,
            diagnostic_code=definition.code,
            question_set_version=definition.version,
            question_count=len(definition.questions),
        )
    return attempt, definition


@transaction.atomic
def submit_diagnostic(user, attempt_id: int, answers: dict[str, object]):
    profile = LearnerIntelligenceProfile.objects.select_for_update().get(user=user)
    attempt = DiagnosticAttempt.objects.select_for_update().get(
        id=attempt_id,
        user=user,
    )
    if attempt.status == "completed":
        return attempt
    expected_stage = next_diagnostic_stage(profile)
    if expected_stage != attempt.stage:
        raise ValidationError("This diagnostic is no longer active.")
    definition = load_diagnostic(attempt.stage, profile)
    if (
        definition.code != attempt.diagnostic_code
        or definition.version != attempt.question_set_version
    ):
        raise ValidationError("The diagnostic version no longer matches.")

    normalized_answers = {}
    for question in definition.questions:
        raw = answers.get(question["id"])
        try:
            selected = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Answer every diagnostic question.") from exc
        if not 0 <= selected < len(question["options"]):
            raise ValidationError("A diagnostic answer is out of range.")
        normalized_answers[question["id"]] = selected

    score = 0
    skills_to_rebuild = {}
    for question in definition.questions:
        selected = normalized_answers[question["id"]]
        is_correct = selected == question["correct"]
        score += int(is_correct)
        skill = Skill.objects.get(code=question["skill"])
        DiagnosticResponse.objects.create(
            attempt=attempt,
            question_id=question["id"],
            skill=skill,
            selected_option=selected,
            is_correct=is_correct,
        )
        record_learning_event(
            user=user,
            skill_code=skill.code,
            event_type="diagnostic_answer",
            source_type="diagnostic",
            source_id=f"{attempt.id}:{question['id']}",
            idempotency_key=f"diagnostic:{attempt.id}:{question['id']}",
            outcome=Decimal("1") if is_correct else Decimal("0"),
            difficulty=question["difficulty"],
            evidence_weight=Decimal("1.100"),
            metadata={
                "diagnostic_code": definition.code,
                "diagnostic_stage": attempt.stage,
            },
            recalculate=False,
        )
        skills_to_rebuild[skill.id] = skill

    attempt.status = "completed"
    attempt.score = score
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "score", "completed_at"])
    if attempt.stage == "routing":
        profile.routing_diagnostic_completed_at = attempt.completed_at
        profile.save(
            update_fields=["routing_diagnostic_completed_at", "updated_at"]
        )
    else:
        profile.goal_diagnostic_completed_at = attempt.completed_at
        profile.save(
            update_fields=["goal_diagnostic_completed_at", "updated_at"]
        )
    for skill in skills_to_rebuild.values():
        rebuild_skill_state(user, skill)
    return attempt
