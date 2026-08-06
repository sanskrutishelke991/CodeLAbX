from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "is_public", "updated_at")
    list_filter = ("is_public",)
    search_fields = ("user__username", "location")
