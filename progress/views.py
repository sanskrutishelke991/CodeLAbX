from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Badge, UserBadge, UserLevel, UserStreak
from .services import BadgeManager


@login_required
def achievements(request):
    """Show all badges (earned + locked)."""
    user = request.user
    
    # Get user's level
    user_level = BadgeManager.get_or_create_user_level(user)
    
    # Get earned badges
    earned_badges = UserBadge.objects.filter(user=user).select_related('badge')
    earned_badge_ids = set(ub.badge.id for ub in earned_badges)
    
    # Get all badges
    all_badges = Badge.objects.all()
    
    # Separate earned and locked
    earned = [ub.badge for ub in earned_badges]
    locked = [b for b in all_badges if b.id not in earned_badge_ids]
    
    # Get user stats
    streak, _ = UserStreak.objects.get_or_create(user=user)
    
    context = {
        'user_level': user_level,
        'earned_badges': earned,
        'locked_badges': locked,
        'total_badges': all_badges.count(),
        'earned_count': len(earned),
        'current_streak': streak.current_streak,
        'longest_streak': streak.longest_streak,
    }
    
    return render(request, 'progress/achievements.html', context)


@login_required
def badge_detail(request, badge_id):
    """Detail of a specific badge."""
    badge = Badge.objects.get(id=badge_id)
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
    """Top users by XP."""
    # Get top 10 users by XP
    top_users = UserLevel.objects.select_related('user').order_by('-total_xp_earned')[:10]
    
    # Get current user's rank
    current_user_level = BadgeManager.get_or_create_user_level(request.user)
    current_rank = UserLevel.objects.filter(
        total_xp_earned__gt=current_user_level.total_xp_earned
    ).count() + 1
    
    context = {
        'top_users': top_users,
        'current_user_level': current_user_level,
        'current_rank': current_rank,
    }
    
    return render(request, 'progress/leaderboard.html', context)


def redirect_to_achievements(request):
    """Redirect root of progress app to achievements."""
    return redirect('progress:achievements')

@login_required
def analytics(request):
    """Comprehensive analytics dashboard"""
    from .services import AnalyticsService
    
    stats = AnalyticsService.get_learning_stats(request.user)
    weekly_activity = AnalyticsService.get_weekly_activity(request.user, weeks=4)
    topic_distribution = AnalyticsService.get_topic_distribution(request.user)
    test_performance = AnalyticsService.get_test_performance(request.user)
    consistency = AnalyticsService.get_study_consistency(request.user)
    
    import json
    
    context = {
        'stats': stats,
        'consistency': consistency,
        'weekly_activity_labels': json.dumps(weekly_activity['labels']),
        'weekly_activity_data': json.dumps(weekly_activity['data']),
        'topic_labels': json.dumps(topic_distribution['labels']),
        'topic_data': json.dumps(topic_distribution['data']),
        'test_labels': json.dumps(test_performance['labels']),
        'test_data': json.dumps(test_performance['data']),
    }
    
    return render(request, 'progress/analytics.html', context)