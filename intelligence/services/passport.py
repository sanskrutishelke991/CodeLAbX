"""Private evidence-observed Skill Passport projections."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from intelligence.models import LearnerIntelligenceProfile, LearningEvent
from intelligence.services.recommendations import SkillDNA, analyze_learning_dna

DETERMINISTIC_EVENT_TYPES = {
    "assessment_answer",
    "challenge_answer",
    "diagnostic_answer",
    "project_rubric",
}


@dataclass(frozen=True)
class EvidenceSourceCount:
    event_type: str
    label: str
    total_count: int
    scoreable_count: int


@dataclass(frozen=True)
class PassportSkill:
    dna: SkillDNA
    total_event_count: int
    scoreable_event_count: int
    deterministic_event_count: int
    supporting_scoreable_count: int
    observed_only_count: int
    sources: tuple[EvidenceSourceCount, ...]

    @property
    def evidence_level(self):
        if self.dna.confidence < Decimal("0.2500"):
            return "Limited evidence"
        if self.dna.confidence < Decimal("0.5500"):
            return "Developing evidence"
        if self.dna.confidence < Decimal("0.8000"):
            return "Supported estimate"
        return "Strong evidence base"


@dataclass(frozen=True)
class SkillPassport:
    skills: tuple[PassportSkill, ...]
    observed_skill_count: int
    unobserved_skill_count: int
    total_event_count: int
    scoreable_event_count: int
    deterministic_event_count: int
    supporting_scoreable_count: int
    observed_only_count: int
    calculated_at: object
    algorithm_version: str


def build_skill_passport(user, profile, *, as_of=None):
    """Build a private passport from ledger records without verification claims."""
    if not isinstance(profile, LearnerIntelligenceProfile):
        raise ValidationError("A learner intelligence profile is required.")
    if profile.user_id != user.id:
        raise ValidationError("The learner profile does not belong to this user.")

    analysis = analyze_learning_dna(user, profile, as_of=as_of)
    skill_ids = [dna.skill.id for dna in analysis.skills]
    rows = list(
        LearningEvent.objects.filter(user=user, skill_id__in=skill_ids)
        .values("skill_id", "event_type")
        .annotate(
            total_count=Count("id"),
            scoreable_count=Count(
                "id",
                filter=Q(outcome__isnull=False),
            ),
        )
        .order_by("skill_id", "event_type")
    )
    labels = dict(LearningEvent.EVENT_TYPES)
    grouped = {}
    for row in rows:
        grouped.setdefault(row["skill_id"], []).append(row)

    passport_skills = []
    for dna in analysis.skills:
        source_rows = grouped.get(dna.skill.id, [])
        total_count = sum(row["total_count"] for row in source_rows)
        scoreable_count = sum(row["scoreable_count"] for row in source_rows)
        deterministic_count = sum(
            row["scoreable_count"]
            for row in source_rows
            if row["event_type"] in DETERMINISTIC_EVENT_TYPES
        )
        supporting_scoreable = max(
            scoreable_count - deterministic_count,
            0,
        )
        observed_only = max(total_count - scoreable_count, 0)
        passport_skills.append(
            PassportSkill(
                dna=dna,
                total_event_count=total_count,
                scoreable_event_count=scoreable_count,
                deterministic_event_count=deterministic_count,
                supporting_scoreable_count=supporting_scoreable,
                observed_only_count=observed_only,
                sources=tuple(
                    EvidenceSourceCount(
                        event_type=row["event_type"],
                        label=labels.get(row["event_type"], row["event_type"]),
                        total_count=row["total_count"],
                        scoreable_count=row["scoreable_count"],
                    )
                    for row in source_rows
                ),
            )
        )

    observed = tuple(
        skill for skill in passport_skills if skill.dna.has_evidence
    )
    return SkillPassport(
        skills=tuple(passport_skills),
        observed_skill_count=len(observed),
        unobserved_skill_count=len(passport_skills) - len(observed),
        total_event_count=sum(skill.total_event_count for skill in passport_skills),
        scoreable_event_count=sum(
            skill.scoreable_event_count for skill in passport_skills
        ),
        deterministic_event_count=sum(
            skill.deterministic_event_count for skill in passport_skills
        ),
        supporting_scoreable_count=sum(
            skill.supporting_scoreable_count for skill in passport_skills
        ),
        observed_only_count=sum(
            skill.observed_only_count for skill in passport_skills
        ),
        calculated_at=analysis.calculated_at,
        algorithm_version=analysis.algorithm_version,
    )
