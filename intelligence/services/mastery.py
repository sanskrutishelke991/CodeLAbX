"""Versioned deterministic mastery, confidence, and freshness calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from intelligence.models import LearningEvent, Skill, SkillState

ALGORITHM_VERSION = "weighted-evidence-v1"
FOUR_PLACES = Decimal("0.0001")
THREE_PLACES = Decimal("0.001")


@dataclass(frozen=True)
class CalculatedSkillState:
    mastery: Decimal
    confidence: Decimal
    freshness: Decimal
    evidence_count: int
    total_evidence_weight: Decimal
    last_evidence_at: datetime | None
    misconception_codes: list[str]


def _bounded_decimal(value: float) -> Decimal:
    bounded = min(1.0, max(0.0, value))
    return Decimal(str(bounded)).quantize(
        FOUR_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _adjusted_weight(event: LearningEvent) -> float:
    base = float(event.evidence_weight)
    difficulty_factor = 0.75 + (0.5 * float(event.difficulty))
    hint_factor = max(0.5, 1 / (1 + (0.2 * event.hints_used)))
    retry_factor = max(0.5, 1 / (1 + (0.15 * event.retry_count)))
    return base * difficulty_factor * hint_factor * retry_factor


def calculate_skill_state(
    events: list[LearningEvent],
    skill: Skill,
    *,
    as_of: datetime | None = None,
) -> CalculatedSkillState:
    """Calculate one reproducible state without AI or mutable hidden inputs."""
    as_of = as_of or timezone.now()
    prior_weight = 2.0
    weighted_success = prior_weight * 0.5
    total_weight = 0.0
    scoreable = []
    misconception_codes = []
    seen_misconceptions = set()

    for event in sorted(events, key=lambda item: (item.occurred_at, item.pk or 0)):
        if event.outcome is None:
            continue
        weight = _adjusted_weight(event)
        total_weight += weight
        weighted_success += weight * float(event.outcome)
        scoreable.append(event)
        if float(event.outcome) < 0.6:
            codes = event.metadata.get("misconception_codes", [])
            if isinstance(codes, list):
                for code in codes:
                    if (
                        isinstance(code, str)
                        and 0 < len(code) <= 80
                        and code not in seen_misconceptions
                    ):
                        seen_misconceptions.add(code)
                        misconception_codes.append(code)

    mastery = weighted_success / (prior_weight + total_weight)
    confidence = 1 - math.exp(-total_weight / 5.0)
    last_evidence = max(
        (event.occurred_at for event in scoreable),
        default=None,
    )
    if last_evidence is None:
        freshness = 0.0
    else:
        elapsed_seconds = max(0.0, (as_of - last_evidence).total_seconds())
        elapsed_days = elapsed_seconds / 86_400
        freshness = math.exp(
            -math.log(2)
            * elapsed_days
            / max(skill.default_half_life_days, 1)
        )

    return CalculatedSkillState(
        mastery=_bounded_decimal(mastery),
        confidence=_bounded_decimal(confidence),
        freshness=_bounded_decimal(freshness),
        evidence_count=len(scoreable),
        total_evidence_weight=Decimal(str(total_weight)).quantize(
            THREE_PLACES,
            rounding=ROUND_HALF_UP,
        ),
        last_evidence_at=last_evidence,
        misconception_codes=misconception_codes[:20],
    )


@transaction.atomic
def rebuild_skill_state(
    user,
    skill: Skill,
    *,
    as_of: datetime | None = None,
) -> SkillState:
    events = list(
        LearningEvent.objects.filter(user=user, skill=skill).order_by(
            "occurred_at",
            "id",
        )
    )
    calculated = calculate_skill_state(events, skill, as_of=as_of)
    state, _ = SkillState.objects.update_or_create(
        user=user,
        skill=skill,
        defaults={
            "mastery": calculated.mastery,
            "confidence": calculated.confidence,
            "freshness": calculated.freshness,
            "evidence_count": calculated.evidence_count,
            "total_evidence_weight": calculated.total_evidence_weight,
            "last_evidence_at": calculated.last_evidence_at,
            "misconception_codes": calculated.misconception_codes,
            "algorithm_version": ALGORITHM_VERSION,
        },
    )
    return state


def rebuild_user_skill_states(user) -> list[SkillState]:
    skill_ids = (
        LearningEvent.objects.filter(user=user)
        .values_list("skill_id", flat=True)
        .distinct()
    )
    skills = Skill.objects.filter(id__in=skill_ids).order_by("code")
    return [rebuild_skill_state(user, skill) for skill in skills]
