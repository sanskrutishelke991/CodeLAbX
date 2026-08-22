from django.contrib import admin

from .models import (
    LearningEvent,
    Skill,
    SkillPack,
    SkillPackMembership,
    SkillPrerequisite,
    SkillState,
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
