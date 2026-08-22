from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

ZERO_TO_ONE = [
    MinValueValidator(Decimal("0")),
    MaxValueValidator(Decimal("1")),
]


class SkillPack(models.Model):
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField()
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"],
                name="unique_skill_pack_version",
            )
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"


class Skill(models.Model):
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField()
    domain = models.CharField(max_length=60)
    difficulty_band = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    default_half_life_days = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain", "code"]
        indexes = [
            models.Index(fields=["domain", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code}: {self.name}"


class SkillPackMembership(models.Model):
    pack = models.ForeignKey(
        SkillPack,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="pack_memberships",
    )
    order = models.PositiveIntegerField()
    is_core = models.BooleanField(default=False)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["pack", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["pack", "skill"],
                name="unique_skill_per_pack",
            ),
            models.UniqueConstraint(
                fields=["pack", "order"],
                name="unique_skill_order_per_pack",
            ),
        ]

    def __str__(self):
        return f"{self.pack.code}: {self.order}. {self.skill.code}"


class SkillPrerequisite(models.Model):
    prerequisite = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="unlocks",
    )
    dependent = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="prerequisites",
    )
    minimum_mastery = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.6000"),
        validators=ZERO_TO_ONE,
    )
    minimum_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.4000"),
        validators=ZERO_TO_ONE,
    )
    strength = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("1.0000"),
        validators=ZERO_TO_ONE,
    )

    class Meta:
        ordering = ["dependent__code", "prerequisite__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["prerequisite", "dependent"],
                name="unique_skill_prerequisite",
            ),
            models.CheckConstraint(
                condition=~Q(prerequisite=F("dependent")),
                name="skill_cannot_require_itself",
            ),
        ]

    def clean(self):
        super().clean()
        if self.prerequisite_id == self.dependent_id:
            raise ValidationError("A skill cannot require itself.")

    def __str__(self):
        return f"{self.prerequisite.code} -> {self.dependent.code}"


class LearningEvent(models.Model):
    EVENT_TYPES = [
        ("assessment_answer", "Assessment answer"),
        ("challenge_answer", "Challenge answer"),
        ("coding_attempt", "Coding attempt"),
        ("lesson_complete", "Lesson completion"),
        ("ai_review", "AI review"),
        ("diagnostic_answer", "Diagnostic answer"),
        ("project_rubric", "Project rubric"),
        ("teach_back", "Tutor teach-back"),
        ("self_report", "Self report"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_events",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="learning_events",
    )
    event_type = models.CharField(max_length=40, choices=EVENT_TYPES)
    source_type = models.CharField(max_length=50)
    source_id = models.CharField(max_length=100)
    idempotency_key = models.CharField(max_length=255)
    outcome = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=ZERO_TO_ONE,
    )
    difficulty = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.5000"),
        validators=ZERO_TO_ONE,
    )
    evidence_weight = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("1.000"),
        validators=[
            MinValueValidator(Decimal("0.001")),
            MaxValueValidator(Decimal("10.000")),
        ],
    )
    hints_used = models.PositiveIntegerField(default=0)
    retry_count = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    schema_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                name="unique_user_learning_event_key",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "skill", "occurred_at"]),
            models.Index(fields=["user", "event_type", "occurred_at"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "Metadata must be an object."})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Learning events are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}:{self.skill.code}:{self.event_type}"


class SkillState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_states",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="user_states",
    )
    mastery = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.5000"),
        validators=ZERO_TO_ONE,
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=ZERO_TO_ONE,
    )
    freshness = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=ZERO_TO_ONE,
    )
    evidence_count = models.PositiveIntegerField(default=0)
    total_evidence_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("0.000"),
    )
    last_evidence_at = models.DateTimeField(null=True, blank=True)
    misconception_codes = models.JSONField(default=list, blank=True)
    algorithm_version = models.CharField(
        max_length=50,
        default="weighted-evidence-v1",
    )
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user", "skill__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill"],
                name="unique_user_skill_state",
            )
        ]
        indexes = [
            models.Index(fields=["user", "mastery"]),
            models.Index(fields=["user", "freshness"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.skill.code} ({self.mastery})"
