from django.contrib import admin
from .models import DailyActivity, UserStreak


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'minutes_studied', 'days_completed', 'activity_level']
    list_filter = ['date', 'user']
    search_fields = ['user__username']


@admin.register(UserStreak)
class UserStreakAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_streak', 'longest_streak', 'total_days_active', 'last_activity_date']
    search_fields = ['user__username']