from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from learning.models import Roadmap
from progress.services import ActivityLogger, BadgeManager
from progress.models import UserBadge


def landing(request):
    """Landing page for non-authenticated users."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'landing.html')


@login_required
def home(request):
    roadmaps = Roadmap.objects.filter(user=request.user, status='active').order_by('-created_at')[:5]
    active_roadmaps = Roadmap.objects.filter(user=request.user, status='active').count()
    
    total_days_completed = 0
    for roadmap in Roadmap.objects.filter(user=request.user):
        total_days_completed += roadmap.completed_days
    
    # Get real stats from activity logger
    stats = ActivityLogger.get_user_stats(request.user)
    
    # Get heatmap data
    heatmap_data = ActivityLogger.get_heatmap_data(request.user, days=365)
    
    # Get user level and badges
    user_level = BadgeManager.get_or_create_user_level(request.user)
    recent_badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')[:3]
    total_badges_earned = UserBadge.objects.filter(user=request.user).count()
    
    context = {
        'roadmaps': roadmaps,
        'active_roadmaps': active_roadmaps,
        'days_completed': total_days_completed,
        'total_hours': stats['total_hours'],
        'current_streak': stats['current_streak'],
        'longest_streak': stats['longest_streak'],
        'user_level': user_level,
        'recent_badges': recent_badges,
        'total_badges_earned': total_badges_earned,
        'heatmap_data': heatmap_data,
    }
    return render(request, 'dashboard/home.html', context)