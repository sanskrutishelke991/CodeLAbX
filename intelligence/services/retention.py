"""Deterministic freshness review analysis and retention missions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from intelligence.models import LearnerIntelligenceProfile, Mission, Skill
from intelligence.services.recommendations import (
    EVIDENCE_POLICY_VERSION,
    SkillDNA,
    analyze_learning_dna,
)

RETENTION_ALGORITHM_VERSION = "freshness-review-v1"
RETENTION_WATCH_THRESHOLD = Decimal("0.7500")
RETENTION_MASTERY_FLOOR = Decimal("0.6000")
RETENTION_CONFIDENCE_FLOOR = Decimal("0.2500")
BLOCKING_MISSION_STATUSES = {"proposed", "accepted", "active", "postponed"}


@dataclass(frozen=True)
class RetentionCandidate:
    dna: SkillDNA
    urgency: str
    urgency_label: str
    days_since_evidence: int
    recommended_checks: int
    expected_minutes: int
    reason: str
    recommendation_key: str


@dataclass(frozen=True)
class RetentionAnalysis:
    candidates: tuple[RetentionCandidate, ...]
    urgent_count: int
    due_count: int
    watch_count: int
    calculated_at: object
    algorithm_version: str = RETENTION_ALGORITHM_VERSION


def _urgency(freshness):
    if freshness <= Decimal("0.3000"):
        return "urgent", "Refresh now", 4
    if freshness <= Decimal("0.5500"):
        return "due", "Review due", 3
    return "watch", "Review soon", 2


def _recommendation_key(profile, dna, urgency):
    payload = {
        "algorithm": RETENTION_ALGORITHM_VERSION,
        "pack": [profile.selected_pack.code, profile.selected_pack.version],
        "skill": dna.skill.code,
        "last_evidence_at": (
            dna.last_evidence_at.isoformat() if dna.last_evidence_at else None
        ),
        "evidence_count": dna.evidence_count,
        "mastery": str(dna.mastery),
        "confidence": str(dna.confidence),
        "urgency": urgency,
    }
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def analyze_retention(user, profile, *, as_of=None):
    """Find previously evidenced skills whose freshness warrants retrieval."""
    if not isinstance(profile, LearnerIntelligenceProfile):
        raise ValidationError("A learner intelligence profile is required.")
    if profile.user_id != user.id:
        raise ValidationError("The learner profile does not belong to this user.")
    as_of = as_of or timezone.now()
    dna = analyze_learning_dna(user, profile, as_of=as_of)
    candidates = []
    for skill_dna in dna.skills:
        if (
            not skill_dna.has_evidence
            or skill_dna.mastery < RETENTION_MASTERY_FLOOR
            or skill_dna.confidence < RETENTION_CONFIDENCE_FLOOR
            or skill_dna.freshness is None
            or skill_dna.freshness >= RETENTION_WATCH_THRESHOLD
        ):
            continue
        urgency, urgency_label, recommended_checks = _urgency(
            skill_dna.freshness
        )
        elapsed = max(
            0.0,
            (as_of - skill_dna.last_evidence_at).total_seconds(),
        )
        days_since_evidence = int(elapsed // 86_400)
        expected_minutes = min(
            45,
            8
            + (skill_dna.skill.difficulty_band * 3)
            + ({"watch": 0, "due": 4, "urgent": 8}[urgency]),
        )
        reason = (
            f"Mastery remains {skill_dna.mastery_percent}% with "
            f"{skill_dna.confidence_percent}% confidence, while retention freshness "
            f"is {skill_dna.freshness_percent}% after {days_since_evidence} day(s)."
        )
        candidates.append(
            RetentionCandidate(
                dna=skill_dna,
                urgency=urgency,
                urgency_label=urgency_label,
                days_since_evidence=days_since_evidence,
                recommended_checks=recommended_checks,
                expected_minutes=expected_minutes,
                reason=reason,
                recommendation_key=_recommendation_key(
                    profile,
                    skill_dna,
                    urgency,
                ),
            )
        )
    candidates.sort(
        key=lambda item: (
            item.dna.freshness,
            -item.dna.confidence,
            item.dna.order,
            item.dna.skill.code,
        )
    )
    return RetentionAnalysis(
        candidates=tuple(candidates),
        urgent_count=sum(item.urgency == "urgent" for item in candidates),
        due_count=sum(item.urgency == "due" for item in candidates),
        watch_count=sum(item.urgency == "watch" for item in candidates),
        calculated_at=as_of,
    )


@transaction.atomic
def create_retention_mission(user, profile, skill, *, as_of=None):
    """Create one idempotent refresh proposal without displacing active work."""
    if not isinstance(skill, Skill):
        raise ValidationError("A valid Skill is required.")
    user.__class__.objects.select_for_update().get(pk=user.pk)
    analysis = analyze_retention(user, profile, as_of=as_of)
    candidate = next(
        (item for item in analysis.candidates if item.dna.skill.id == skill.id),
        None,
    )
    if candidate is None:
        raise ValidationError(
            "That skill does not currently meet the evidence and freshness rules for a refresh mission."
        )

    existing = (
        Mission.objects.select_for_update()
        .filter(
            user=user,
            recommendation_key=candidate.recommendation_key,
        )
        .first()
    )
    if existing is not None:
        return existing, False, candidate

    blocker = (
        Mission.objects.select_for_update()
        .filter(user=user, status__in=BLOCKING_MISSION_STATUSES)
        .order_by("-created_at")
        .first()
    )
    if blocker is not None:
        raise ValidationError(
            f'Decide or finish the current mission “{blocker.title}” before adding a refresh mission.'
        )

    mission = Mission.objects.create(
        user=user,
        primary_skill=skill,
        mission_type="retention",
        status="proposed",
        title=f"Refresh {skill.name}",
        description=(
            "Use short retrieval practice in an existing challenge or assessment "
            "workflow. This refresh targets recency; it does not lower the separate "
            "mastery estimate."
        ),
        rationale={
            "algorithm_version": RETENTION_ALGORITHM_VERSION,
            "reason_codes": ["RETENTION_DUE"],
            "skill_code": skill.code,
            "mastery": str(candidate.dna.mastery),
            "confidence": str(candidate.dna.confidence),
            "freshness": str(candidate.dna.freshness),
            "evidence_count": candidate.dna.evidence_count,
            "days_since_evidence": candidate.days_since_evidence,
            "urgency": candidate.urgency,
            "calculated_at": analysis.calculated_at.isoformat(),
        },
        success_criteria={
            "minimum_scoreable_events": candidate.recommended_checks,
            "skill_code": skill.code,
            "completion_rule": (
                "Recalculate after new scoreable evidence. Completion is not "
                "inferred from XP, lesson clicks, or AI prose."
            ),
        },
        expected_minutes=candidate.expected_minutes,
        evidence_policy_version=EVIDENCE_POLICY_VERSION,
        recommendation_key=candidate.recommendation_key,
    )
    return mission, True, candidate
