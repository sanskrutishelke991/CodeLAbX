from django.contrib import admin

from .models import (
    DiagnosticAttempt,
    DiagnosticResponse,
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    PublicShare,
    RoadmapNode,
    RoadmapRevision,
    Skill,
    SkillPack,
    SkillPackMembership,
    SkillPrerequisite,
    SkillState,
    TutorFeedback,
    TutorMemory,
    TutorPreference,
)


class SkillPackMembershipInline(admin.TabularInline):
    model = SkillPackMembership
    extra = 0
    autocomplete_fields = ["skill"]


@admin.register(SkillPack)
class SkillPackAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "is_active", "updated_at")
    list_filter = ("is_active", "version")
    search_fields = ("code", "name")
    inlines = [SkillPackMembershipInline]


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "domain",
        "difficulty_band",
        "default_half_life_days",
        "is_active",
    )
    list_filter = ("domain", "difficulty_band", "is_active")
    search_fields = ("code", "name", "description")


@admin.register(SkillPackMembership)
class SkillPackMembershipAdmin(admin.ModelAdmin):
    list_display = ("pack", "order", "skill", "is_core", "is_required")
    list_filter = ("pack", "is_core", "is_required")
    search_fields = ("pack__code", "skill__code", "skill__name")
    autocomplete_fields = ["pack", "skill"]


@admin.register(SkillPrerequisite)
class SkillPrerequisiteAdmin(admin.ModelAdmin):
    list_display = (
        "prerequisite",
        "dependent",
        "minimum_mastery",
        "minimum_confidence",
        "strength",
    )
    autocomplete_fields = ["prerequisite", "dependent"]


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "skill",
        "event_type",
        "outcome",
        "evidence_weight",
        "occurred_at",
    )
    list_filter = ("event_type", "skill__domain", "schema_version")
    search_fields = (
        "user__username",
        "skill__code",
        "source_type",
        "source_id",
        "idempotency_key",
    )
    readonly_fields = [field.name for field in LearningEvent._meta.fields]
    date_hierarchy = "occurred_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SkillState)
class SkillStateAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "skill",
        "mastery",
        "confidence",
        "freshness",
        "evidence_count",
        "calculated_at",
    )
    list_filter = ("skill__domain", "algorithm_version")
    search_fields = ("user__username", "skill__code", "skill__name")
    readonly_fields = ("calculated_at",)


@admin.register(LearnerIntelligenceProfile)
class LearnerIntelligenceProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "primary_goal",
        "selected_pack",
        "routing_diagnostic_completed_at",
        "goal_diagnostic_completed_at",
    )
    list_filter = ("primary_goal", "selected_pack")
    search_fields = ("user__username", "user__email", "custom_goal")
    autocomplete_fields = ["user", "selected_pack"]


class DiagnosticResponseInline(admin.TabularInline):
    model = DiagnosticResponse
    extra = 0
    readonly_fields = (
        "question_id",
        "skill",
        "selected_option",
        "is_correct",
        "answered_at",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DiagnosticAttempt)
class DiagnosticAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "stage",
        "diagnostic_code",
        "status",
        "score",
        "question_count",
        "completed_at",
    )
    list_filter = ("stage", "status", "diagnostic_code")
    search_fields = ("user__username", "diagnostic_code")
    readonly_fields = ("started_at", "completed_at")
    inlines = [DiagnosticResponseInline]


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "primary_skill",
        "mission_type",
        "status",
        "expected_minutes",
        "created_at",
    )
    list_filter = ("mission_type", "status", "primary_skill__domain")
    search_fields = (
        "user__username",
        "primary_skill__code",
        "primary_skill__name",
        "title",
    )
    autocomplete_fields = ["user", "primary_skill", "additional_skills"]
    readonly_fields = (
        "recommendation_key",
        "created_at",
        "updated_at",
    )


class RoadmapNodeInline(admin.TabularInline):
    model = RoadmapNode
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in RoadmapNode._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(RoadmapRevision)
class RoadmapRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "roadmap",
        "revision_number",
        "status",
        "reason_code",
        "trigger_mission",
        "created_at",
    )
    list_filter = ("status", "reason_code", "algorithm_version")
    search_fields = (
        "roadmap__title",
        "roadmap__user__username",
        "summary",
    )
    readonly_fields = [field.name for field in RoadmapRevision._meta.fields]
    inlines = [RoadmapNodeInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RoadmapNode)
class RoadmapNodeAdmin(admin.ModelAdmin):
    list_display = (
        "revision",
        "order",
        "skill",
        "status",
        "is_user_locked",
        "mission",
    )
    list_filter = ("status", "is_user_locked", "skill__domain")
    search_fields = (
        "revision__roadmap__title",
        "revision__roadmap__user__username",
        "skill__code",
        "skill__name",
    )
    readonly_fields = [field.name for field in RoadmapNode._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DiagnosticResponse)
class DiagnosticResponseAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question_id",
        "skill",
        "selected_option",
        "is_correct",
    )
    list_filter = ("is_correct", "skill__domain")
    search_fields = (
        "attempt__user__username",
        "question_id",
        "skill__code",
    )
    readonly_fields = [field.name for field in DiagnosticResponse._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TutorPreference)
class TutorPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "teaching_mode",
        "explanation_depth",
        "preferred_language",
        "observed_adaptation_enabled",
        "updated_at",
    )
    list_filter = (
        "teaching_mode",
        "explanation_depth",
        "preferred_language",
        "observed_adaptation_enabled",
    )
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ["user"]
    readonly_fields = ("created_at", "updated_at", "onboarding_completed_at")


@admin.register(TutorMemory)
class TutorMemoryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "category",
        "source_type",
        "is_active",
        "user_confirmed",
        "updated_at",
    )
    list_filter = ("category", "source_type", "is_active", "user_confirmed")
    search_fields = ("user__username", "content", "reason")
    autocomplete_fields = ["user"]
    raw_id_fields = ["chat_session"]
    readonly_fields = ("source_key", "created_at", "updated_at")


@admin.register(TutorFeedback)
class TutorFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "feedback_type", "updated_at")
    list_filter = ("feedback_type",)
    search_fields = ("user__username", "message__session__title")
    readonly_fields = [field.name for field in TutorFeedback._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PublicShare)
class PublicShareAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "share_type",
        "public_id",
        "is_active",
        "created_at",
        "refreshed_at",
        "revoked_at",
    )
    list_filter = ("share_type", "is_active")
    search_fields = ("user__username", "display_name", "public_id")
    readonly_fields = [field.name for field in PublicShare._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
