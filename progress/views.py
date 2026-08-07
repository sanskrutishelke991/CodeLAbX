from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from .models import Badge, UserBadge, UserLevel, UserStreak
from .services import BadgeManager


@login_required
def achievements(request):
    """Enhanced achievements page with real data"""
    from .models import Badge, UserBadge, UserLevel, UserStreak
    from django.db.models import Count, Q

    # Get user progress
    user_level, _ = UserLevel.objects.get_or_create(user=request.user)
    user_streak, _ = UserStreak.objects.get_or_create(user=request.user)

    # All badges with earned status
    all_badges = Badge.objects.all().order_by('category', 'requirement_value')
    earned_badge_ids = UserBadge.objects.filter(user=request.user).values_list('badge_id', flat=True)

    # Categorize badges
    categorized = {
        'streak': [],
        'learning': [],
        'practice': [],
        'test': [],
        'special': [],
    }

    for badge in all_badges:
        is_earned = badge.id in earned_badge_ids
        earned_at = None
        if is_earned:
            try:
                user_badge = UserBadge.objects.get(user=request.user, badge=badge)
                earned_at = user_badge.earned_at
            except:
                pass

        badge_data = {
            'badge': badge,
            'is_earned': is_earned,
            'earned_at': earned_at,
        }

        if badge.category in categorized:
            categorized[badge.category].append(badge_data)

    # Stats
    total_badges = all_badges.count()
    earned_count = len(earned_badge_ids)
    completion_rate = round((earned_count / max(total_badges, 1)) * 100, 1)

    # Recent unlocks (last 5)
    recent_unlocks = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')[:5]

    # Next to unlock (locked badges with lowest requirement)
    next_to_unlock = []
    for badge in all_badges:
        if badge.id not in earned_badge_ids:
            next_to_unlock.append(badge)
            if len(next_to_unlock) >= 3:
                break

    # Rarity counts
    rarity_stats = {
        'common': all_badges.filter(rarity='common').count(),
        'rare': all_badges.filter(rarity='rare').count(),
        'epic': all_badges.filter(rarity='epic').count(),
        'legendary': all_badges.filter(rarity='legendary').count(),
    }

    earned_by_rarity = {
        'common': UserBadge.objects.filter(user=request.user, badge__rarity='common').count(),
        'rare': UserBadge.objects.filter(user=request.user, badge__rarity='rare').count(),
        'epic': UserBadge.objects.filter(user=request.user, badge__rarity='epic').count(),
        'legendary': UserBadge.objects.filter(user=request.user, badge__rarity='legendary').count(),
    }

    # XP progress
    current_xp = user_level.current_xp
    next_level_xp = user_level.xp_for_next_level
    level_progress = user_level.level_progress_percentage

    # Category filter
    category_filter = request.GET.get('category', 'all')

    context = {
        'user_level': user_level,
        'user_streak': user_streak,
        'categorized': categorized,
        'total_badges': total_badges,
        'earned_count': earned_count,
        'completion_rate': completion_rate,
        'recent_unlocks': recent_unlocks,
        'next_to_unlock': next_to_unlock,
        'rarity_stats': rarity_stats,
        'earned_by_rarity': earned_by_rarity,
        'current_xp': current_xp,
        'next_level_xp': next_level_xp,
        'level_progress': level_progress,
        'category_filter': category_filter,
    }

    return render(request, 'progress/achievements.html', context)



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
