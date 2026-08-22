from __future__ import annotations

import json
import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

ZERO_TO_ONE = [
    MinValueValidator(Decimal("0")),
    MaxValueValidator(Decimal("1")),
]
MISSION_JSON_MAX_BYTES = 8192
TUTOR_JSON_MAX_BYTES = 2048
TUTOR_MEMORY_MAX_CHARS = 600
TUTOR_ACCESSIBILITY_KEYS = {
    "avoid_emoji",
    "prefer_checklists",
    "reduce_cognitive_load",
}
LIKELY_SECRET_PATTERNS = (
    re.compile(
        r"\b(?:api[_ -]?key|password|secret|access[_ -]?token)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
)


def _validate_mission_json(value, field_name):
    if not isinstance(value, dict):
        raise ValidationError({field_name: "This value must be an object."})
    try:
        encoded = json.dumps(
            value,
            cls=DjangoJSONEncoder,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            {field_name: "This value must be JSON serializable."}
        ) from exc
    if len(encoded) > MISSION_JSON_MAX_BYTES:
        raise ValidationError(
            {field_name: "This value exceeds the 8 KB limit."}
        )


def _validate_tutor_accessibility(value):
    if not isinstance(value, dict):
        raise ValidationError(
            {"accessibility_preferences": "This value must be an object."}
        )
    if set(value) - TUTOR_ACCESSIBILITY_KEYS:
        raise ValidationError(
            {"accessibility_preferences": "An unsupported accessibility key was used."}
        )
    if any(not isinstance(item, bool) for item in value.values()):
        raise ValidationError(
            {"accessibility_preferences": "Accessibility values must be true or false."}
        )
    encoded = json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > TUTOR_JSON_MAX_BYTES:
        raise ValidationError(
            {"accessibility_preferences": "This value exceeds the 2 KB limit."}
        )


def _validate_memory_text(value, field_name):
    if any(pattern.search(value) for pattern in LIKELY_SECRET_PATTERNS):
        raise ValidationError(
            {
                field_name: (
                    "Tutor memory cannot store likely credentials, API keys, "
                    "passwords, secrets, or access tokens."
                )
            }
        )


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


class LearnerIntelligenceProfile(models.Model):
    GOAL_CHOICES = [
        ("semester", "Semester learning"),
        ("placement", "Placement and interview preparation"),
        ("project", "Project building"),
        ("machine_learning", "Machine learning"),
        ("fullstack", "Full-stack development"),
        ("custom", "Custom goal"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intelligence_profile",
    )
    primary_goal = models.CharField(max_length=40, choices=GOAL_CHOICES)
    custom_goal = models.CharField(max_length=300, blank=True)
    selected_pack = models.ForeignKey(
        SkillPack,
        on_delete=models.PROTECT,
        related_name="learner_profiles",
    )
    routing_diagnostic_completed_at = models.DateTimeField(null=True, blank=True)
    goal_diagnostic_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.primary_goal == "custom" and not self.custom_goal.strip():
            raise ValidationError({"custom_goal": "Describe the custom goal."})
        if len(self.custom_goal) > 300:
            raise ValidationError({"custom_goal": "Custom goal is too long."})

    @property
    def diagnostics_complete(self):
        return bool(
            self.routing_diagnostic_completed_at
            and self.goal_diagnostic_completed_at
        )

    def __str__(self):
        return f"{self.user}: {self.get_primary_goal_display()}"


class DiagnosticAttempt(models.Model):
    STAGE_CHOICES = [
        ("routing", "Routing diagnostic"),
        ("goal", "Goal-specific diagnostic"),
    ]
    STATUS_CHOICES = [
        ("started", "Started"),
        ("completed", "Completed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diagnostic_attempts",
    )
    pack = models.ForeignKey(
        SkillPack,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="diagnostic_attempts",
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    diagnostic_code = models.CharField(max_length=100)
    question_set_version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="started",
    )
    score = models.PositiveIntegerField(default=0)
    question_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "stage", "status"]),
        ]

    @property
    def percentage(self):
        if not self.question_count:
            return 0
        return round(self.score / self.question_count * 100, 1)

    def __str__(self):
        return f"{self.user}: {self.diagnostic_code} ({self.status})"


class DiagnosticResponse(models.Model):
    attempt = models.ForeignKey(
        DiagnosticAttempt,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    question_id = models.CharField(max_length=100)
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="diagnostic_responses",
    )
    selected_option = models.PositiveIntegerField()
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question_id"],
                name="unique_diagnostic_response",
            )
        ]

    def __str__(self):
        return f"{self.attempt_id}:{self.question_id}"


class Mission(models.Model):
    TYPE_CHOICES = [
        ("diagnostic", "Diagnostic"),
        ("learn", "Learn"),
        ("practice", "Practice"),
        ("remediation", "Remediation"),
        ("retention", "Retention"),
        ("project", "Project"),
        ("stretch", "Stretch"),
    ]
    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("accepted", "Accepted"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("postponed", "Postponed"),
        ("skipped", "Skipped"),
        ("expired", "Expired"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intelligence_missions",
    )
    primary_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="primary_missions",
    )
    additional_skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name="supporting_missions",
    )
    mission_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="proposed",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=1200)
    rationale = models.JSONField(default=dict)
    success_criteria = models.JSONField(default=dict)
    expected_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(240)]
    )
    evidence_policy_version = models.CharField(
        max_length=60,
        default="weighted-evidence-v1",
    )
    recommendation_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    postponed_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recommendation_key"],
                name="unique_user_recommendation_key",
            ),
            models.CheckConstraint(
                condition=Q(expected_minutes__gte=5)
                & Q(expected_minutes__lte=240),
                name="mission_expected_minutes_range",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
        ]

    def clean(self):
        super().clean()
        _validate_mission_json(self.rationale, "rationale")
        _validate_mission_json(self.success_criteria, "success_criteria")
        if len(self.description) > 1200:
            raise ValidationError(
                {"description": "Description exceeds 1,200 characters."}
            )
        if self.status == "postponed" and self.postponed_until is None:
            raise ValidationError(
                {"postponed_until": "A postponed mission needs a review date."}
            )
        if self.status != "postponed" and self.postponed_until is not None:
            raise ValidationError(
                {"postponed_until": "Only postponed missions have a review date."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}:{self.primary_skill.code}:{self.status}"


class RoadmapRevision(models.Model):
    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("active", "Active"),
        ("postponed", "Postponed"),
        ("rejected", "Rejected"),
        ("superseded", "Superseded"),
    ]
    REASON_CHOICES = [
        ("initial_skill_route", "Initial skill route"),
        ("mission_proposal", "Mission proposal"),
        ("restored_revision", "Restored revision"),
    ]

    roadmap = models.ForeignKey(
        "learning.Roadmap",
        on_delete=models.CASCADE,
        related_name="intelligence_revisions",
    )
    revision_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reason_code = models.CharField(max_length=40, choices=REASON_CHOICES)
    summary = models.CharField(max_length=800)
    input_state_version = models.CharField(max_length=64)
    input_state_at = models.DateTimeField()
    algorithm_version = models.CharField(max_length=60)
    based_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_revisions",
    )
    trigger_mission = models.ForeignKey(
        Mission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roadmap_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    postponed_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["roadmap", "-revision_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["roadmap", "revision_number"],
                name="unique_roadmap_revision_number",
            ),
            models.UniqueConstraint(
                fields=["roadmap"],
                condition=Q(status="active"),
                name="one_active_revision_per_roadmap",
            ),
            models.UniqueConstraint(
                fields=["roadmap"],
                condition=Q(status="proposed"),
                name="one_proposed_revision_per_roadmap",
            ),
            models.CheckConstraint(
                condition=Q(revision_number__gte=1),
                name="roadmap_revision_number_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["roadmap", "status", "revision_number"]),
        ]

    def clean(self):
        super().clean()
        if self.trigger_mission_id and (
            self.trigger_mission.user_id != self.roadmap.user_id
        ):
            raise ValidationError(
                {"trigger_mission": "Mission and roadmap owners must match."}
            )
        if self.based_on_id and self.based_on.roadmap_id != self.roadmap_id:
            raise ValidationError(
                {"based_on": "A revision can only derive from the same roadmap."}
            )
        if self.status == "postponed" and self.postponed_until is None:
            raise ValidationError(
                {"postponed_until": "A postponed revision needs a review date."}
            )
        if self.status != "postponed" and self.postponed_until is not None:
            raise ValidationError(
                {"postponed_until": "Only postponed revisions have a review date."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.roadmap_id}: revision {self.revision_number} ({self.status})"


class RoadmapNode(models.Model):
    STATUS_CHOICES = [
        ("locked", "Prerequisite locked"),
        ("ready", "Ready"),
        ("active", "Active"),
        ("complete", "Complete"),
        ("skipped", "Skipped"),
    ]

    revision = models.ForeignKey(
        RoadmapRevision,
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="roadmap_nodes",
    )
    mission = models.ForeignKey(
        Mission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roadmap_nodes",
    )
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    rationale = models.CharField(max_length=1000)
    expected_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(240)]
    )
    is_user_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["revision", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "order"],
                name="unique_node_order_per_revision",
            ),
            models.UniqueConstraint(
                fields=["revision", "skill"],
                name="unique_skill_per_revision",
            ),
            models.CheckConstraint(
                condition=Q(order__gte=1),
                name="roadmap_node_order_positive",
            ),
            models.CheckConstraint(
                condition=Q(expected_minutes__gte=5)
                & Q(expected_minutes__lte=240),
                name="roadmap_node_expected_minutes_range",
            ),
        ]
        indexes = [
            models.Index(fields=["revision", "status", "order"]),
        ]

    def clean(self):
        super().clean()
        if self.mission_id and (
            self.mission.user_id != self.revision.roadmap.user_id
        ):
            raise ValidationError(
                {"mission": "Mission and roadmap owners must match."}
            )
        if self.mission_id and self.mission.primary_skill_id != self.skill_id:
            raise ValidationError(
                {"mission": "A node mission must target the node's skill."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.revision_id}:{self.order}:{self.skill.code}"


class TutorPreference(models.Model):
    EXPLANATION_DEPTH_CHOICES = [
        ("concise", "Concise"),
        ("balanced", "Balanced"),
        ("detailed", "Detailed"),
    ]
    TEACHING_MODE_CHOICES = [
        ("direct", "Direct explanation"),
        ("example_first", "Example first"),
        ("socratic", "Socratic questions"),
        ("mixed", "Mixed"),
    ]
    CODE_DENSITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    LANGUAGE_CHOICES = [
        ("english", "English"),
        ("hindi", "Hindi"),
        ("hinglish", "Hinglish"),
        ("marathi", "Marathi"),
    ]
    PACE_CHOICES = [
        ("gentle", "Gentle"),
        ("steady", "Steady"),
        ("fast", "Fast"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_preference",
    )
    explanation_depth = models.CharField(
        max_length=20,
        choices=EXPLANATION_DEPTH_CHOICES,
        default="balanced",
    )
    teaching_mode = models.CharField(
        max_length=20,
        choices=TEACHING_MODE_CHOICES,
        default="mixed",
    )
    code_density = models.CharField(
        max_length=20,
        choices=CODE_DENSITY_CHOICES,
        default="medium",
    )
    preferred_language = models.CharField(
        max_length=20,
        choices=LANGUAGE_CHOICES,
        default="english",
    )
    pace = models.CharField(
        max_length=20,
        choices=PACE_CHOICES,
        default="steady",
    )
    session_minutes = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(10), MaxValueValidator(120)],
    )
    accessibility_preferences = models.JSONField(default=dict, blank=True)
    learning_context_enabled = models.BooleanField(default=True)
    observed_adaptation_enabled = models.BooleanField(default=False)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(session_minutes__gte=10)
                & Q(session_minutes__lte=120),
                name="tutor_session_minutes_range",
            )
        ]

    def clean(self):
        super().clean()
        _validate_tutor_accessibility(self.accessibility_preferences)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}: {self.teaching_mode}/{self.explanation_depth}"


class TutorMemory(models.Model):
    CATEGORY_CHOICES = [
        ("goal", "Goal"),
        ("misconception", "Misconception to revisit"),
        ("preference", "Teaching preference"),
        ("project", "Current project"),
        ("revisit", "Topic to revisit"),
        ("session_summary", "Session summary"),
    ]
    SOURCE_CHOICES = [
        ("explicit_user", "Added by learner"),
        ("observed_feedback", "Suggested from repeated feedback"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_memories",
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    content = models.TextField(max_length=TUTOR_MEMORY_MAX_CHARS)
    reason = models.CharField(max_length=300)
    source_type = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="explicit_user",
    )
    source_key = models.CharField(max_length=120, blank=True)
    chat_session = models.ForeignKey(
        "ai_tools.ChatSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tutor_memories",
    )
    is_active = models.BooleanField(default=True)
    user_confirmed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source_key"],
                condition=~Q(source_key=""),
                name="unique_user_tutor_memory_source",
            ),
            models.UniqueConstraint(
                fields=["user", "chat_session"],
                condition=Q(category="session_summary"),
                name="unique_tutor_session_summary",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active", "category"]),
        ]

    def clean(self):
        super().clean()
        self.content = self.content.strip()
        self.reason = self.reason.strip()
        if not self.content:
            raise ValidationError({"content": "Tutor memory cannot be empty."})
        if not self.reason:
            raise ValidationError({"reason": "Explain why this memory is stored."})
        _validate_memory_text(self.content, "content")
        _validate_memory_text(self.reason, "reason")
        if self.category == "session_summary" and self.chat_session_id is None:
            raise ValidationError(
                {"chat_session": "A session summary must reference your chat session."}
            )
        if self.category != "session_summary" and self.chat_session_id is not None:
            raise ValidationError(
                {"chat_session": "Only session summaries reference a chat session."}
            )
        if self.chat_session_id and self.chat_session.user_id != self.user_id:
            raise ValidationError(
                {"chat_session": "Tutor memory and chat session owners must match."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}:{self.category}:{self.content[:40]}"


class TutorFeedback(models.Model):
    FEEDBACK_CHOICES = [
        ("helped", "Helpful"),
        ("too_fast", "Too fast"),
        ("too_detailed", "Too detailed"),
        ("more_examples", "More examples"),
        ("more_code", "More code"),
        ("ask_me_questions", "Ask me questions"),
        ("already_known", "I already knew this"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_feedback",
    )
    message = models.ForeignKey(
        "ai_tools.ChatMessage",
        on_delete=models.CASCADE,
        related_name="tutor_feedback",
    )
    feedback_type = models.CharField(max_length=30, choices=FEEDBACK_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "message"],
                name="unique_tutor_feedback_per_message",
            )
        ]
        indexes = [
            models.Index(fields=["user", "feedback_type", "updated_at"]),
        ]

    def clean(self):
        super().clean()
        if self.message_id and self.message.session.user_id != self.user_id:
            raise ValidationError(
                {"message": "Tutor feedback and chat message owners must match."}
            )
        if self.message_id and self.message.role != "assistant":
            raise ValidationError(
                {"message": "Feedback can only target an assistant response."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}:{self.message_id}:{self.feedback_type}"
