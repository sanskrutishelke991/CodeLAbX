from django.contrib import admin

from .models import EmailPreference, UserProfile, WeeklyReportDelivery


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
