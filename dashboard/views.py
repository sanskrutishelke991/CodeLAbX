from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from learning.models import Roadmap
from progress.services import ActivityLogger, BadgeManager
from progress.models import UserBadge
from django.urls import reverse


def landing(request):
    """Landing page for non-authenticated users."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'landing.html')


def _next_day(rm):
    nxt = None
    has_days = False
    for day in rm.days.all():
        has_days = True
        if not day.is_completed:
            nxt = day
            break
    if nxt is not None:
        return nxt.day_number, False
    if has_days:
        return rm.total_days, True
    return 1, False


@login_required
def home(request):
    roadmaps = list(
        Roadmap.objects.filter(user=request.user)
        .exclude(status='archived')
        .order_by('-created_at')
        .prefetch_related('days')
    )
    roadmaps.sort(key=lambda r: 0 if r.status == 'active' else 1)
    for rm in roadmaps:
        num, done = _next_day(rm)
        rm.next_day_number = num
        rm.next_is_done = done
    active_roadmaps = sum(1 for r in roadmaps if r.status == 'active')

    total_days_completed = 0
    for roadmap in Roadmap.objects.filter(user=request.user):
        total_days_completed += roadmap.completed_days

    stats = ActivityLogger.get_user_stats(request.user)
    heatmap_data = ActivityLogger.get_heatmap_data(request.user, days=365)
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


def privacy(request):
    return render(request, 'legal/privacy.html')


def terms(request):
    return render(request, 'legal/terms.html')
