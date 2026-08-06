from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from assessments.models import Test
from challenges.models import Challenge, UserChallenge
from content.models import UserVideoProgress
from learning.models import Day, Roadmap
from progress.models import UserBadge, XPTransaction
from progress.services import ActivityLogger, BadgeManager


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return render(request, "landing.html")


@login_required
def home(request):
    user = request.user

    roadmaps = list(
        Roadmap.objects.filter(user=user, status="active")
        .annotate(
            dashboard_completed_days=Count(
                "days",
                filter=Q(days__is_completed=True),
                distinct=True,
            )
        )
        .order_by("-updated_at")[:3]
    )
    for roadmap in roadmaps:
        roadmap.dashboard_progress = (
            round(
                roadmap.dashboard_completed_days
                * 100
                / roadmap.total_days,
                1,
            )
            if roadmap.total_days
            else 0
        )
        roadmap.next_day = (
            roadmap.days.filter(is_completed=False)
            .order_by("order")
            .first()
        )

    all_roadmaps = Roadmap.objects.filter(user=user)
    active_roadmaps = all_roadmaps.filter(status="active").count()
    completed_roadmaps = all_roadmaps.filter(status="completed").count()
    days_completed = Day.objects.filter(
        roadmap__user=user,
        is_completed=True,
    ).count()

    stats = ActivityLogger.get_user_stats(user)
    heatmap_data = ActivityLogger.get_heatmap_data(user, days=365)
    total_active_days = sum(1 for item in heatmap_data if item["level"] > 0)

    user_level = BadgeManager.get_or_create_user_level(user)
    recent_badges = list(
        UserBadge.objects.filter(user=user)
        .select_related("badge")
        .order_by("-earned_at")[:6]
    )
    total_badges = UserBadge.objects.filter(user=user).count()
    recent_activity = list(
        XPTransaction.objects.filter(user=user)
        .order_by("-created_at")[:8]
    )

    today = timezone.localdate()
    today_challenges = list(
        Challenge.objects.filter(date=today).order_by("challenge_type")
    )
    challenge_attempts = {
        attempt.challenge_id: attempt
        for attempt in UserChallenge.objects.filter(
            user=user,
            challenge__in=today_challenges,
        )
    }
    challenge_cards = [
        {
            "challenge": challenge,
            "attempt": challenge_attempts.get(challenge.id),
        }
        for challenge in today_challenges
    ]

    context = {
        "today": today,
        "roadmaps": roadmaps,
        "active_roadmaps": active_roadmaps,
        "completed_roadmaps": completed_roadmaps,
        "days_completed": days_completed,
        "total_hours": stats["total_hours"],
        "current_streak": stats["current_streak"],
        "longest_streak": stats["longest_streak"],
        "total_active_days": total_active_days,
        "user_level": user_level,
        "recent_badges": recent_badges,
        "total_badges_earned": total_badges,
        "recent_activity": recent_activity,
        "heatmap_data": heatmap_data,
        "challenge_cards": challenge_cards,
        "tests_completed": Test.objects.filter(
            user=user,
            status="completed",
        ).count(),
        "videos_watched": UserVideoProgress.objects.filter(
            user=user,
            is_watched=True,
        ).count(),
    }
    return render(request, "dashboard/home.html", context)
