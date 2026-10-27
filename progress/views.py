from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from .models import Badge, UserBadge, UserLevel, UserStreak
from .services import BadgeManager


@login_required
def achievements(request):
    """Render badge progress without per-badge database lookups."""
    user_level, _ = UserLevel.objects.get_or_create(user=request.user)
    user_streak, _ = UserStreak.objects.get_or_create(user=request.user)
    all_badges = list(
        Badge.objects.all().order_by("category", "requirement_value")
    )
    earned_badges = list(
        UserBadge.objects.filter(user=request.user)
        .select_related("badge")
        .order_by("-earned_at")
    )
    earned_by_badge_id = {
        item.badge_id: item
        for item in earned_badges
    }

    categorized = {
        "streak": [],
        "learning": [],
        "practice": [],
        "test": [],
        "special": [],
    }
    rarity_stats = {
        "common": 0,
        "rare": 0,
        "epic": 0,
        "legendary": 0,
    }
    earned_by_rarity = {key: 0 for key in rarity_stats}

    for badge in all_badges:
        earned = earned_by_badge_id.get(badge.id)
        rarity_stats[badge.rarity] += 1
        if earned:
            earned_by_rarity[badge.rarity] += 1
        if badge.category in categorized:
            categorized[badge.category].append(
                {
                    "badge": badge,
                    "is_earned": earned is not None,
                    "earned_at": earned.earned_at if earned else None,
                }
            )

    next_to_unlock = [
        badge
        for badge in all_badges
        if badge.id not in earned_by_badge_id
    ][:3]
    total_badges = len(all_badges)
    earned_count = len(earned_badges)

    return render(
        request,
        "progress/achievements.html",
        {
            "user_level": user_level,
            "user_streak": user_streak,
            "categorized": categorized,
            "total_badges": total_badges,
            "earned_count": earned_count,
            "completion_rate": round(
                earned_count / max(total_badges, 1) * 100,
                1,
            ),
            "recent_unlocks": earned_badges[:5],
            "next_to_unlock": next_to_unlock,
            "rarity_stats": rarity_stats,
            "earned_by_rarity": earned_by_rarity,
            "current_xp": user_level.current_xp,
            "next_level_xp": user_level.xp_for_next_level(),
            "level_progress": user_level.level_progress_percentage(),
            "category_filter": request.GET.get("category", "all"),
        },
    )



@login_required
def badge_detail(request, badge_id):
    """Detail of a specific badge."""
    badge = get_object_or_404(Badge, id=badge_id)
    user = request.user

    # Check if user has earned this badge
    user_badge = UserBadge.objects.filter(user=user, badge=badge).first()

    # Calculate progress for locked badges
    progress = 0
    if not user_badge:
        progress = BadgeManager.get_badge_progress(user, badge)

    context = {
        'badge': badge,
        'user_badge': user_badge,
        'progress': progress,
    }

    return render(request, 'progress/badge_detail.html', context)


@login_required
def leaderboard(request):
    """Display public learners ranked by total XP."""
    current_user_level = (
        BadgeManager.get_or_create_user_level(request.user)
    )

    eligible_levels = UserLevel.objects.filter(
        Q(user__profile__is_public=True)
        | Q(user=request.user)
    )

    users = (
        eligible_levels
        .select_related('user', 'user__profile')
        .annotate(
            badge_count=Count(
                'user__badges',
                distinct=True,
            )
        )
        .order_by(
            '-total_xp_earned',
            'user__username',
        )[:10]
    )

    current_rank = (
        eligible_levels.filter(
            total_xp_earned__gt=(
                current_user_level.total_xp_earned
            )
        ).count()
        + 1
    )

    context = {
        'users': users,
        'top_users': users,
        'current_user_level': current_user_level,
        'current_rank': current_rank,
    }

    return render(
        request,
        'progress/leaderboard.html',
        context,
    )


def redirect_to_achievements(request):
    """Redirect root of progress app to achievements."""
    return redirect('progress:achievements')

@login_required
def analytics(request):
    """Render analytics using bounded, real user data."""
    from .services import AnalyticsService

    stats = AnalyticsService.get_learning_stats(request.user)
    weekly_activity = AnalyticsService.get_weekly_activity(request.user, weeks=4)
    topic_distribution = AnalyticsService.get_topic_distribution(request.user)
    test_performance = AnalyticsService.get_test_performance(request.user)
    consistency = AnalyticsService.get_study_consistency(request.user)

    context = {
        "stats": stats,
        "consistency": consistency,
        "consistency_remaining": max(0, round(100 - consistency, 1)),
        "weekly_activity_labels": weekly_activity["labels"],
        "weekly_activity_data": weekly_activity["data"],
        "topic_labels": topic_distribution["labels"],
        "topic_data": topic_distribution["data"],
        "test_labels": test_performance["labels"],
        "test_data": test_performance["data"],
        "has_topic_data": bool(topic_distribution["labels"]),
        "has_test_data": bool(test_performance["labels"]),
    }

    return render(request, "progress/analytics.html", context)

@login_required
def analytics_export(request):
    """Export the signed-in learner's bounded analytics as CSV."""
    import csv

    from django.http import HttpResponse
    from django.utils import timezone

    from .services import AnalyticsService

    stats = AnalyticsService.get_learning_stats(request.user)
    weekly = AnalyticsService.get_weekly_activity(request.user, weeks=4)
    topics = AnalyticsService.get_topic_distribution(request.user)
    tests = AnalyticsService.get_test_performance(request.user)
    consistency = AnalyticsService.get_study_consistency(request.user)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="codelabx-analytics-'
        f'{timezone.localdate().isoformat()}.csv"'
    )
    response["Cache-Control"] = "no-store"
    writer = csv.writer(response)
    writer.writerow(["CodeLabX analytics export"])
    writer.writerow(["Generated at", timezone.now().isoformat()])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    metric_rows = [
        ("Recorded study hours", stats["total_hours"]),
        ("Recorded activity days", stats["total_activity_days"]),
        ("Completed roadmap days", stats["completed_days"]),
        ("Total roadmap days", stats["total_days"]),
        ("Current streak", stats["current_streak"]),
        ("Longest streak", stats["longest_streak"]),
        ("Completed tests", stats["total_tests"]),
        ("30-day consistency percent", consistency),
    ]
    writer.writerows(metric_rows)
    writer.writerow([])
    writer.writerow(["Activity date", "Recorded minutes"])
    writer.writerows(zip(weekly["labels"], weekly["data"], strict=True))
    writer.writerow([])
    writer.writerow(["Roadmap topic", "Completed days"])
    writer.writerows(zip(topics["labels"], topics["data"], strict=True))
    writer.writerow([])
    writer.writerow(["Test date", "Score percent"])
    writer.writerows(zip(tests["labels"], tests["data"], strict=True))
    return response
