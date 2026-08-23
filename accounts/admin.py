from django.contrib import admin

from .models import (
    EmailPreference,
    GitHubConnection,
    GitHubRepository,
    UserProfile,
    WeeklyReportDelivery,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "is_public", "updated_at")
    list_filter = ("is_public",)
    search_fields = ("user__username", "location")


@admin.register(EmailPreference)
class EmailPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "weekly_report_enabled",
        "report_weekday",
        "updated_at",
    )
    list_filter = ("weekly_report_enabled", "report_weekday")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ["user"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(WeeklyReportDelivery)
class WeeklyReportDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "period_start",
        "period_end",
        "status",
        "attempt_count",
        "sent_at",
    )
    list_filter = ("status", "period_end")
    search_fields = ("user__username", "user__email", "subject")
    readonly_fields = [field.name for field in WeeklyReportDelivery._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class GitHubRepositoryInline(admin.TabularInline):
    model = GitHubRepository
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in GitHubRepository._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(GitHubConnection)
class GitHubConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "username", "status", "public_repos", "fetched_at")
    list_filter = ("status",)
    search_fields = ("user__username", "username", "display_name")
    readonly_fields = (
        "github_user_id",
        "profile_url",
        "display_name",
        "bio",
        "public_repos",
        "followers",
        "status",
        "last_error_code",
        "fetched_at",
        "created_at",
        "updated_at",
    )
    inlines = [GitHubRepositoryInline]


@admin.register(GitHubRepository)
class GitHubRepositoryAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "language",
        "stargazers_count",
        "forks_count",
        "pushed_at",
    )
    list_filter = ("language", "is_fork")
    search_fields = ("full_name", "description", "connection__user__username")
    readonly_fields = [field.name for field in GitHubRepository._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
