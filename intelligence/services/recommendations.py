"""Deterministic Learning DNA analysis and mission recommendations."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from intelligence.models import (
    LearnerIntelligenceProfile,
    Mission,
    SkillPrerequisite,
    SkillState,
)

RECOMMENDATION_ALGORITHM_VERSION = "prerequisite-priority-v1"
EVIDENCE_POLICY_VERSION = "weighted-evidence-v1"
TARGET_MASTERY = Decimal("0.7000")
TARGET_CONFIDENCE = Decimal("0.5500")
REVIEW_FRESHNESS = Decimal("0.6000")
FOUR_PLACES = Decimal("0.0001")

REASON_MESSAGES = {
    "NO_EVIDENCE": "No scoreable evidence has been recorded for this skill yet.",
    "LOW_CONFIDENCE": "The current estimate has limited evidence and needs calibration.",
    "SKILL_GAP": "The evidence-backed mastery estimate is below the current target.",
    "REVIEW_DUE": "Recent-evidence freshness is below the review threshold.",
    "CORE_FOUNDATION": "This is a core foundation in the selected Skill Pack.",
    "UNLOCKS_NEXT": "Strengthening this skill helps unlock later skills in the pack.",
    "PREREQUISITES_READY": "The recorded prerequisites currently meet their thresholds.",
}


@dataclass(frozen=True)
class SkillDNA:
    skill: object
    order: int
    is_core: bool
    is_required: bool
    mastery: Decimal | None
    confidence: Decimal
    freshness: Decimal | None
    evidence_count: int
    total_evidence_weight: Decimal
    last_evidence_at: datetime | None
    algorithm_version: str

    @property
    def has_evidence(self):
        return self.evidence_count > 0 and self.mastery is not None

    @property
    def mastery_percent(self):
        return _percentage(self.mastery)

    @property
    def confidence_percent(self):
        return _percentage(self.confidence)

    @property
    def freshness_percent(self):
        return _percentage(self.freshness)

    @property
    def confidence_label(self):
        if self.confidence < Decimal("0.2500"):
            return "Limited evidence"
        if self.confidence < Decimal("0.5500"):
            return "Developing evidence"
        if self.confidence < Decimal("0.8000"):
            return "Supported estimate"
        return "Strong evidence base"


@dataclass(frozen=True)
class CandidateAnalysis:
    dna: SkillDNA
    eligible: bool
    unmet_prerequisites: tuple[str, ...]
    unmet_prerequisite_names: tuple[str, ...]
    unlock_codes: tuple[str, ...]
    unlock_names: tuple[str, ...]
    priority: Decimal
    reason_codes: tuple[str, ...]
    reason_messages: tuple[str, ...]
    mission_type: str
    expected_minutes: int
    title: str
    description: str


@dataclass(frozen=True)
class LearningDNAAnalysis:
    skills: tuple[SkillDNA, ...]
    candidates: tuple[CandidateAnalysis, ...]
    recommendation: CandidateAnalysis | None
    alternatives: tuple[CandidateAnalysis, ...]
    observed_skill_count: int
    scoreable_evidence_count: int
    calculated_at: datetime
    recommendation_key: str | None
    algorithm_version: str = RECOMMENDATION_ALGORITHM_VERSION



def _percentage(value: Decimal | None):
    if value is None:
        return None
    return int(
        (value * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _bounded_decimal(value: float) -> Decimal:
    return Decimal(str(min(1.0, max(0.0, value)))).quantize(
        FOUR_PLACES,
        rounding=ROUND_HALF_UP,
    )


def effective_freshness(state, skill, *, as_of=None):
    """Return time-current freshness without rewriting derived snapshots."""
    as_of = as_of or timezone.now()
    if state is None or state.last_evidence_at is None or not state.evidence_count:
        return None
    elapsed_seconds = max(
        0.0,
        (as_of - state.last_evidence_at).total_seconds(),
    )
    elapsed_days = elapsed_seconds / 86_400
    value = math.exp(
        -math.log(2)
        * elapsed_days
        / max(skill.default_half_life_days, 1)
    )
    return _bounded_decimal(value)


def _state_to_dna(membership, state, *, as_of):
    has_evidence = state is not None and state.evidence_count > 0
    return SkillDNA(
        skill=membership.skill,
        order=membership.order,
        is_core=membership.is_core,
        is_required=membership.is_required,
        mastery=state.mastery if has_evidence else None,
        confidence=state.confidence if has_evidence else Decimal("0.0000"),
        freshness=effective_freshness(
            state,
            membership.skill,
            as_of=as_of,
        ),
        evidence_count=state.evidence_count if state else 0,
        total_evidence_weight=(
            state.total_evidence_weight if state else Decimal("0.000")
        ),
        last_evidence_at=state.last_evidence_at if state else None,
        algorithm_version=(
            state.algorithm_version if state else EVIDENCE_POLICY_VERSION
        ),
    )


def _relation_is_met(relation, state):
    return bool(
        state
        and state.evidence_count > 0
        and state.mastery >= relation.minimum_mastery
        and state.confidence >= relation.minimum_confidence
    )


def _mission_type(dna):
    if not dna.has_evidence:
        return "diagnostic"
    if (
        dna.freshness is not None
        and dna.freshness < Decimal("0.4500")
        and dna.mastery >= Decimal("0.6500")
    ):
        return "retention"
    if dna.mastery < Decimal("0.5000"):
        return "remediation"
    if dna.mastery < TARGET_MASTERY or dna.confidence < TARGET_CONFIDENCE:
        return "practice"
    return "stretch"


def _mission_copy(dna, mission_type):
    name = dna.skill.name
    titles = {
        "diagnostic": f"Calibrate {name}",
        "remediation": f"Repair the {name} foundation",
        "retention": f"Refresh {name}",
        "practice": f"Strengthen {name}",
        "stretch": f"Stretch {name}",
    }
    descriptions = {
        "diagnostic": (
            "Complete a short set of scoreable checks so CodeLabX can replace "
            "the neutral prior with evidence."
        ),
        "remediation": (
            "Review the key concept, work through a guided example, then complete "
            "focused checks without treating mistakes as failure."
        ),
        "retention": (
            "Use a compact retrieval session to refresh older evidence while "
            "preserving the separate mastery estimate."
        ),
        "practice": (
            "Complete focused practice and one explain-back check to strengthen "
            "both mastery evidence and confidence."
        ),
        "stretch": (
            "Apply this supported skill in a harder mixed problem to extend the "
            "current evidence base."
        ),
    }
    base_minutes = {
        "diagnostic": 12,
        "remediation": 25,
        "retention": 12,
        "practice": 18,
        "stretch": 25,
    }
    step_minutes = {
        "diagnostic": 2,
        "remediation": 5,
        "retention": 3,
        "practice": 4,
        "stretch": 5,
    }
    expected_minutes = min(
        60,
        base_minutes[mission_type]
        + (step_minutes[mission_type] * dna.skill.difficulty_band),
    )
    return (
        titles[mission_type],
        descriptions[mission_type],
        expected_minutes,
    )


def _reason_codes(dna, *, has_prerequisites, unlock_count):
    reasons = []
    if not dna.has_evidence:
        reasons.append("NO_EVIDENCE")
    if dna.confidence < TARGET_CONFIDENCE:
        reasons.append("LOW_CONFIDENCE")
    if not dna.has_evidence or dna.mastery < TARGET_MASTERY:
        reasons.append("SKILL_GAP")
    if (
        dna.has_evidence
        and dna.freshness is not None
        and dna.freshness < REVIEW_FRESHNESS
    ):
        reasons.append("REVIEW_DUE")
    if dna.is_core:
        reasons.append("CORE_FOUNDATION")
    if unlock_count:
        reasons.append("UNLOCKS_NEXT")
    if has_prerequisites:
        reasons.append("PREREQUISITES_READY")
    return tuple(reasons)


def _priority(dna, *, unlock_count):
    internal_mastery = dna.mastery if dna.mastery is not None else Decimal("0.5000")
    gap = max(TARGET_MASTERY - internal_mastery, Decimal("0.0500"))
    if not dna.has_evidence:
        gap = max(gap, Decimal("0.3500"))
    evidence_need = Decimal("1") + (
        (Decimal("1") - dna.confidence) * Decimal("0.70")
    )
    relevance = Decimal("1")
    if dna.is_required:
        relevance += Decimal("0.05")
    if dna.is_core:
        relevance += Decimal("0.15")
    review_multiplier = Decimal("1")
    if dna.has_evidence and dna.freshness is not None:
        review_gap = max(REVIEW_FRESHNESS - dna.freshness, Decimal("0"))
        review_multiplier += review_gap
    unlock_multiplier = Decimal("1") + min(
        Decimal("0.50"),
        Decimal(unlock_count) * Decimal("0.08"),
    )
    return (
        gap
        * evidence_need
        * relevance
        * review_multiplier
        * unlock_multiplier
    ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _recommendation_key(profile, recommendation, skills):
    if recommendation is None:
        return None
    signature = {
        "algorithm": RECOMMENDATION_ALGORITHM_VERSION,
        "pack": [profile.selected_pack.code, profile.selected_pack.version],
        "goal": [profile.primary_goal, profile.custom_goal],
        "recommendation": [
            recommendation.dna.skill.code,
            recommendation.mission_type,
            list(recommendation.reason_codes),
        ],
        "skills": [
            {
                "code": dna.skill.code,
                "mastery": str(dna.mastery) if dna.mastery is not None else None,
                "confidence": str(dna.confidence),
                "evidence_count": dna.evidence_count,
                "last_evidence_at": (
                    dna.last_evidence_at.isoformat() if dna.last_evidence_at else None
                ),
                "review_due": bool(
                    dna.freshness is not None
                    and dna.freshness < REVIEW_FRESHNESS
                ),
            }
            for dna in skills
        ],
    }
    encoded = json.dumps(
        signature,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def analyze_learning_dna(user, profile, *, as_of=None):
    """Build one private, evidence-backed profile and eligible recommendation."""
    if not isinstance(profile, LearnerIntelligenceProfile):
        raise ValidationError("A learner intelligence profile is required.")
    if profile.user_id != user.id:
        raise ValidationError("The learner profile does not belong to this user.")
    as_of = as_of or timezone.now()
    memberships = list(
        profile.selected_pack.memberships.filter(skill__is_active=True)
        .select_related("skill")
        .order_by("order", "skill__code")
    )
    skill_ids = [membership.skill_id for membership in memberships]
    relations = list(
        SkillPrerequisite.objects.filter(dependent_id__in=skill_ids)
        .select_related("prerequisite", "dependent")
        .order_by("dependent__code", "prerequisite__code")
    )
    related_skill_ids = set(skill_ids)
    related_skill_ids.update(relation.prerequisite_id for relation in relations)
    states = {
        state.skill_id: state
        for state in SkillState.objects.filter(
            user=user,
            skill_id__in=related_skill_ids,
        ).select_related("skill")
    }
    dna_skills = tuple(
        _state_to_dna(
            membership,
            states.get(membership.skill_id),
            as_of=as_of,
        )
        for membership in memberships
    )
    prerequisites_by_skill = {}
    unlocks_by_skill = {}
    pack_skill_ids = set(skill_ids)
    for relation in relations:
        prerequisites_by_skill.setdefault(relation.dependent_id, []).append(relation)
        if relation.prerequisite_id in pack_skill_ids:
            unlocks_by_skill.setdefault(relation.prerequisite_id, []).append(relation)

    candidates = []
    for dna in dna_skills:
        prerequisites = prerequisites_by_skill.get(dna.skill.id, [])
        unmet = [
            relation
            for relation in prerequisites
            if not _relation_is_met(
                relation,
                states.get(relation.prerequisite_id),
            )
        ]
        unlocks = unlocks_by_skill.get(dna.skill.id, [])
        eligible = not unmet
        mission_type = _mission_type(dna)
        title, description, expected_minutes = _mission_copy(dna, mission_type)
        reasons = _reason_codes(
            dna,
            has_prerequisites=bool(prerequisites),
            unlock_count=len(unlocks),
        )
        candidates.append(
            CandidateAnalysis(
                dna=dna,
                eligible=eligible,
                unmet_prerequisites=tuple(
                    relation.prerequisite.code for relation in unmet
                ),
                unmet_prerequisite_names=tuple(
                    relation.prerequisite.name for relation in unmet
                ),
                unlock_codes=tuple(
                    relation.dependent.code for relation in unlocks
                ),
                unlock_names=tuple(
                    relation.dependent.name for relation in unlocks
                ),
                priority=(
                    _priority(dna, unlock_count=len(unlocks))
                    if eligible
                    else Decimal("0.0000")
                ),
                reason_codes=reasons,
                reason_messages=tuple(REASON_MESSAGES[code] for code in reasons),
                mission_type=mission_type,
                expected_minutes=expected_minutes,
                title=title,
                description=description,
            )
        )

    ranked = sorted(
        (candidate for candidate in candidates if candidate.eligible),
        key=lambda candidate: (
            -candidate.priority,
            candidate.dna.order,
            candidate.dna.skill.code,
        ),
    )
    recommendation = ranked[0] if ranked else None
    alternatives = tuple(ranked[1:3])
    recommendation_key = _recommendation_key(
        profile,
        recommendation,
        dna_skills,
    )
    return LearningDNAAnalysis(
        skills=dna_skills,
        candidates=tuple(candidates),
        recommendation=recommendation,
        alternatives=alternatives,
        observed_skill_count=sum(dna.has_evidence for dna in dna_skills),
        scoreable_evidence_count=sum(dna.evidence_count for dna in dna_skills),
        calculated_at=as_of,
        recommendation_key=recommendation_key,
    )


def _mission_rationale(analysis):
    recommendation = analysis.recommendation
    dna = recommendation.dna
    return {
        "algorithm_version": analysis.algorithm_version,
        "reason_codes": list(recommendation.reason_codes),
        "reason_messages": list(recommendation.reason_messages),
        "skill_code": dna.skill.code,
        "mastery": str(dna.mastery) if dna.mastery is not None else None,
        "confidence": str(dna.confidence),
        "freshness": str(dna.freshness) if dna.freshness is not None else None,
        "evidence_count": dna.evidence_count,
        "priority": str(recommendation.priority),
        "unlocks": list(recommendation.unlock_codes),
        "alternatives": [item.dna.skill.code for item in analysis.alternatives],
        "calculated_at": analysis.calculated_at.isoformat(),
    }


def _success_criteria(recommendation):
    event_target = {
        "diagnostic": 3,
        "retention": 3,
        "remediation": 5,
        "practice": 5,
        "stretch": 4,
    }[recommendation.mission_type]
    return {
        "minimum_scoreable_events": event_target,
        "target_mastery": str(TARGET_MASTERY),
        "target_confidence": str(TARGET_CONFIDENCE),
        "completion_rule": (
            "Recalculate after the required scoreable evidence; mission completion "
            "is not inferred from XP or AI prose."
        ),
    }


@transaction.atomic
def propose_next_mission(user, profile, *, as_of=None):
    """Persist one idempotent proposal and expire a superseded proposal."""
    analysis = analyze_learning_dna(user, profile, as_of=as_of)
    recommendation = analysis.recommendation
    if recommendation is None or analysis.recommendation_key is None:
        raise ValidationError("No eligible mission can be recommended.")

    current = list(
        Mission.objects.select_for_update().filter(
            user=user,
            status="proposed",
        )
    )
    mission = Mission.objects.filter(
        user=user,
        recommendation_key=analysis.recommendation_key,
    ).first()
    created = mission is None
    if mission is None:
        mission = Mission(
            user=user,
            primary_skill=recommendation.dna.skill,
            recommendation_key=analysis.recommendation_key,
        )
    mission.primary_skill = recommendation.dna.skill
    mission.mission_type = recommendation.mission_type
    mission.status = "proposed"
    mission.title = recommendation.title
    mission.description = recommendation.description
    mission.rationale = _mission_rationale(analysis)
    mission.success_criteria = _success_criteria(recommendation)
    mission.expected_minutes = recommendation.expected_minutes
    mission.evidence_policy_version = EVIDENCE_POLICY_VERSION
    mission.decided_at = None
    mission.save()

    Mission.objects.filter(
        id__in=[item.id for item in current if item.id != mission.id]
    ).update(status="expired", decided_at=analysis.calculated_at)
    mission.additional_skills.set(
        [item.dna.skill for item in analysis.alternatives]
    )
    return mission, created, analysis
