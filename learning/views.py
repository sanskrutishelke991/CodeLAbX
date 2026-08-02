import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Roadmap, Day
from .forms import RoadmapCreateForm
from .services import RoadmapGenerator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from ai_tools.api import provider_error_response, safe_api_errors
from ai_tools.security import protect_ai_endpoint
from ai_tools.services import GeminiService

logger = logging.getLogger(__name__)


@login_required
def roadmap_list(request):
    """Display all roadmaps for the current user with real stats."""
    from django.db.models import Sum, Count, Q, Avg
    from datetime import timedelta
    from django.utils import timezone
    
    # Get filter params
    status_filter = request.GET.get('status', 'all')
    topic_filter = request.GET.get('topic', 'all')
    difficulty_filter = request.GET.get('difficulty', 'all')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'recent')
    view_mode = request.GET.get('view', 'grid')
    
    # Base queryset
    roadmaps = Roadmap.objects.filter(user=request.user)
    
    # Apply filters
    if status_filter != 'all':
        roadmaps = roadmaps.filter(status=status_filter)
    
    if topic_filter != 'all':
        roadmaps = roadmaps.filter(topic=topic_filter)
    
    if difficulty_filter != 'all':
        roadmaps = roadmaps.filter(level=difficulty_filter)
    
    if search_query:
        roadmaps = roadmaps.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'recent':
        roadmaps = roadmaps.order_by('-created_at')
    elif sort_by == 'progress':
        roadmaps = list(roadmaps)
        roadmaps.sort(key=lambda x: x.progress_percentage, reverse=True)
    elif sort_by == 'name':
        roadmaps = roadmaps.order_by('title')
    elif sort_by == 'duration':
        roadmaps = roadmaps.order_by('-total_days')
    
    # Calculate real statistics
    all_user_roadmaps = Roadmap.objects.filter(user=request.user)
    
    total_paths = all_user_roadmaps.count()
    active_paths = all_user_roadmaps.filter(status='active').count()
    completed_paths = all_user_roadmaps.filter(status='completed').count()
    paused_paths = all_user_roadmaps.filter(status='paused').count()
    
    # Total days completed across all roadmaps
    total_days_completed = 0
    total_days_planned = 0
    total_hours_studied = 0
    
    for roadmap in all_user_roadmaps:
        total_days_completed += roadmap.completed_days
        total_days_planned += roadmap.total_days
        total_hours_studied += roadmap.completed_days * float(roadmap.daily_hours)
    
    # Average progress
    if all_user_roadmaps.exists():
        avg_progress = sum(r.progress_percentage for r in all_user_roadmaps) / all_user_roadmaps.count()
    else:
        avg_progress = 0
    
    # Get streak from progress app if available
    current_streak = 0
    try:
        from progress.models import UserStreak
        streak_obj = UserStreak.objects.filter(user=request.user).first()
        if streak_obj:
            current_streak = streak_obj.current_streak
    except:
        pass
    
    # Get available topics for filter
    available_topics = all_user_roadmaps.values_list('topic', flat=True).distinct()
    
    # Get available difficulties
    available_difficulties = all_user_roadmaps.values_list('level', flat=True).distinct()
    
    # Recently updated roadmap (for "Continue" quick action)
    recent_roadmap = all_user_roadmaps.filter(status='active').order_by('-updated_at').first()
    
    context = {
        'roadmaps': roadmaps,
        'total_paths': total_paths,
        'active_paths': active_paths,
        'completed_paths': completed_paths,
        'paused_paths': paused_paths,
        'total_days_completed': total_days_completed,
        'total_days_planned': total_days_planned,
        'total_hours_studied': round(total_hours_studied, 1),
        'avg_progress': round(avg_progress, 1),
        'current_streak': current_streak,
        'available_topics': available_topics,
        'available_difficulties': available_difficulties,
        'recent_roadmap': recent_roadmap,
        'status_filter': status_filter,
        'topic_filter': topic_filter,
        'difficulty_filter': difficulty_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'view_mode': view_mode,
    }
    
    return render(request, 'learning/roadmap_list.html', context)


@login_required
def roadmap_create(request):
    """Create a new learning roadmap."""
    if request.method == 'POST':
        form = RoadmapCreateForm(request.POST)
        if form.is_valid():
            try:
                roadmap = RoadmapGenerator.generate_roadmap(
                    user=request.user,
                    topic=form.cleaned_data['topic'],
                    duration_months=form.cleaned_data['duration_months'],
                    daily_hours=form.cleaned_data['daily_hours'],
                    level=form.cleaned_data['level'],
                    start_date=form.cleaned_data.get('start_date')
                )
                
                if form.cleaned_data.get('description'):
                    roadmap.description = form.cleaned_data['description']
                    roadmap.save()
                
                # Award XP for creating first roadmap
                try:
                    from progress.services import BadgeManager
                    BadgeManager.add_xp(
                        request.user,
                        25,
                        "Created roadmap",
                        idempotency_key=f"roadmap-created:{roadmap.id}",
                        event_type="roadmap-created",
                        source_object_type="roadmap",
                        source_object_id=roadmap.id,
                    )
                    BadgeManager.check_and_award_badges(request.user)
                except Exception as e:
                    print(f"Badge error: {e}")
                
                messages.success(request, f'Roadmap "{roadmap.title}" created successfully with {roadmap.total_days} days!')
                return redirect('learning:roadmap_detail', roadmap_id=roadmap.id)
                
            except Exception as e:
                messages.error(request, f'Error creating roadmap: {str(e)}')
    else:
        form = RoadmapCreateForm()
    
    available_topics = RoadmapGenerator.get_available_topics()
    
    return render(request, 'learning/roadmap_create.html', {
        'form': form,
        'available_topics': available_topics
    })


@login_required
def roadmap_detail(request, roadmap_id):
    """Display detail view of a specific roadmap with timeline."""
    roadmap = get_object_or_404(Roadmap, id=roadmap_id, user=request.user)
    days = roadmap.days.all().order_by('order')
    
    return render(request, 'learning/roadmap_detail.html', {
        'roadmap': roadmap,
        'days': days
    })


@login_required
def day_detail(request, roadmap_id, day_number):
    """Display detail view for a specific day in a roadmap."""
    roadmap = get_object_or_404(Roadmap, id=roadmap_id, user=request.user)
    day = get_object_or_404(Day, roadmap=roadmap, day_number=day_number)
    
    return render(request, 'learning/day_detail.html', {
        'roadmap': roadmap,
        'day': day
    })


@login_required
@require_POST
@protect_ai_endpoint(
    "day-content",
    "AI_GENERATION_BURST_LIMIT",
)
@safe_api_errors
def generate_day_content(
    request,
    roadmap_id,
    day_number,
):
    """Generate sanitized content for an owned day."""
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )

    day = get_object_or_404(
        Day,
        roadmap=roadmap,
        day_number=day_number,
    )

    result = (
        GeminiService()
        .generate_theory(
            day.title,
            level=roadmap.level,
        )
    )

    if not result.get("success"):
        return provider_error_response(
            logger,
            "day-content",
            result.get("error"),
        )

    day.ai_content = result["content_html"]
    day.ai_content_generated_at = (
        timezone.now()
    )

    day.save(
        update_fields=[
            "ai_content",
            "ai_content_generated_at",
        ]
    )

    return JsonResponse(
        {
            "success": True,
            "content": result["content_html"],
        }
    )


@login_required
@require_POST
@transaction.atomic
def mark_day_complete(request, roadmap_id, day_number):
    """Complete a roadmap day exactly once."""
    from progress.services import ActivityLogger, BadgeManager

    roadmap = get_object_or_404(
        Roadmap.objects.select_for_update(),
        id=roadmap_id,
        user=request.user,
    )
    day = get_object_or_404(
        Day.objects.select_for_update(),
        roadmap=roadmap,
        day_number=day_number,
    )

    if day.is_completed:
        return JsonResponse(
            {
                "success": True,
                "already_completed": True,
                "message": f"Day {day.day_number} was already completed.",
                "xp_earned": 0,
            }
        )

    day.is_completed = True
    day.completed_at = timezone.now()
    day.save(update_fields=["is_completed", "completed_at"])
    ActivityLogger.log_day_completion(request.user, day)

    xp_result = BadgeManager.add_xp(
        request.user,
        20,
        "Completed a day",
        idempotency_key=f"day-completed:{day.id}",
        event_type="day-completed",
        source_object_type="day",
        source_object_id=day.id,
    )
    new_badges = BadgeManager.check_and_award_badges(request.user)

    if not roadmap.days.filter(is_completed=False).exists():
        roadmap.status = "completed"
        roadmap.end_date = timezone.localdate()
        roadmap.save(update_fields=["status", "end_date", "updated_at"])

    return JsonResponse(
        {
            "success": True,
            "already_completed": False,
            "message": f"Day {day.day_number} marked as complete!",
            "xp_earned": xp_result["xp_added"],
            "xp_reason": "Day completed",
            "leveled_up": xp_result["leveled_up"],
            "new_level": xp_result["new_level"],
            "new_badges": [
                {
                    "name": getattr(item, "badge", item).name,
                    "icon": getattr(item, "badge", item).icon,
                }
                for item in new_badges
            ],
            "roadmap_completed": roadmap.status == "completed",
        }
    )

