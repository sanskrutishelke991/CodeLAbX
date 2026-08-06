from django.contrib import admin

from .models import (
    Badge,
    DailyActivity,
    UserBadge,
    UserLevel,
    UserStreak,
    XPTransaction,
)

admin.site.register(Badge)
admin.site.register(DailyActivity)
admin.site.register(UserBadge)
admin.site.register(UserLevel)
admin.site.register(UserStreak)
admin.site.register(XPTransaction)
