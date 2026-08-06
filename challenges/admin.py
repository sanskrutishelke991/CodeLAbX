from django.contrib import admin

from .models import Challenge, ChallengeStreak, UserChallenge

admin.site.register(Challenge)
admin.site.register(UserChallenge)
admin.site.register(ChallengeStreak)
