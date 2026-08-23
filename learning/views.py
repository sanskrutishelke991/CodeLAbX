import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai_tools.api import provider_error_response, safe_api_errors
from ai_tools.security import protect_ai_endpoint
from ai_tools.services import GeminiService
from intelligence.services.emitters import emit_day_completion
from progress.models import UserStreak
from progress.services import BadgeManager

from .forms import RoadmapCreateForm
from .models import Day, Roadmap
from .services import RoadmapGenerator


logger = logging.getLogger(__name__)


@login_required
def roadmap_list(request):
    """Display all roadmaps for the current user with real stats."""
    # Get filter params
    status_filter = request.GET.get('status', 'all')
    topic_filter = request.GET.get('topic', 'all')
    difficulty_filter = request.GET.get('difficulty', 'all')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'recent')
    view_mode = request.GET.get('view', 'grid')
    
    # Base queryset
    roadmaps = Roadmap.objects.filter(user=request.user).annotate(
        completed_days_count=Count(
            "days",
            filter=Q(days__is_completed=True),
        )
    )
    
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
    all_user_roadmaps = Roadmap.objects.filter(user=request.user).annotate(
        completed_days_count=Count(
            "days",
            filter=Q(days__is_completed=True),
        )
    )
    
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
    
    streak_obj = UserStreak.objects.filter(user=request.user).first()
    current_streak = streak_obj.current_streak if streak_obj else 0
    
    # Get available topics for filter
    available_topics = all_user_roadmaps.values_list('topic', flat=True).distinct()
    
    # Get available difficulties
    available_difficulties = all_user_roadmaps.values_list('level', flat=True).distinct()
    
    # Recently updated roadmap (for "Continue" quick action)
    recent_roadmap = all_user_roadmaps.filter(status='active').order_by('-updated_at').first()
    
    page_obj = Paginator(roadmaps, 9).get_page(request.GET.get('page'))

    context = {
        'roadmaps': page_obj,
        'page_obj': page_obj,
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
                with transaction.atomic():
                    roadmap = RoadmapGenerator.generate_roadmap(
                        user=request.user,
                        topic=form.cleaned_data["topic"],
                        duration_months=form.cleaned_data["duration_months"],
                        daily_hours=form.cleaned_data["daily_hours"],
                        level=form.cleaned_data["level"],
                        start_date=form.cleaned_data.get("start_date"),
                    )
                    description = form.cleaned_data.get("description")
                    if description:
                        roadmap.description = description
                        roadmap.save(
                            update_fields=["description", "updated_at"]
                        )
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
            except Exception:
                logger.exception(
                    "Roadmap creation rolled back",
                    extra={"user_id": request.user.pk},
                )
                messages.error(
                    request,
                    "The roadmap could not be created. No changes were saved.",
                )
            else:
                messages.success(
                    request,
                    f'Roadmap "{roadmap.title}" created with '
                    f"{roadmap.total_days} days.",
                )
                return redirect(
                    "learning:roadmap_detail",
                    roadmap_id=roadmap.id,
                )
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
    from intelligence.models import RoadmapRevision

    roadmap = get_object_or_404(Roadmap, id=roadmap_id, user=request.user)
    days = roadmap.days.all().order_by('order')
    adaptive_revisions = list(
        RoadmapRevision.objects.filter(
            roadmap=roadmap,
            status__in={"active", "proposed"},
        ).order_by("-revision_number")
    )
    adaptive_active = next(
        (item for item in adaptive_revisions if item.status == "active"),
        None,
    )
    adaptive_proposed = next(
        (item for item in adaptive_revisions if item.status == "proposed"),
        None,
    )

    return render(request, 'learning/roadmap_detail.html', {
        'roadmap': roadmap,
        'days': days,
        'adaptive_active': adaptive_active,
        'adaptive_proposed': adaptive_proposed,
    })


@login_required
def day_detail(request, roadmap_id, day_number):
    """Display an owned day plus private owner comments and group links."""
    from community.forms import DayCommentForm
    from community.models import DayComment, GroupRoadmapShare

    roadmap = get_object_or_404(Roadmap, id=roadmap_id, user=request.user)
    day = get_object_or_404(Day, roadmap=roadmap, day_number=day_number)
    personal_comments = DayComment.objects.filter(
        day=day,
        group__isnull=True,
        author=request.user,
    ).order_by("created_at")
    group_shares = (
        GroupRoadmapShare.objects.filter(
            roadmap=roadmap,
            group__memberships__user=request.user,
        )
        .select_related("group")
        .distinct()
    )
    return render(request, 'learning/day_detail.html', {
        'roadmap': roadmap,
        'day': day,
        'personal_comments': personal_comments,
        'day_comment_form': DayCommentForm(),
        'group_shares': group_shares,
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

    emit_day_completion(request.user, day)

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



@login_required
@require_POST
def roadmap_action(request, roadmap_id, action):
    """Apply an owner-authorized roadmap lifecycle action."""
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )

    if action == "pause" and roadmap.status == "active":
        roadmap.status = "paused"
        roadmap.save(update_fields=["status", "updated_at"])
        messages.success(request, "Roadmap paused.")
    elif action == "resume" and roadmap.status in {"paused", "archived"}:
        roadmap.status = "active"
        roadmap.save(update_fields=["status", "updated_at"])
        messages.success(request, "Roadmap resumed.")
    elif action == "archive" and roadmap.status != "archived":
        roadmap.status = "archived"
        roadmap.save(update_fields=["status", "updated_at"])
        messages.success(request, "Roadmap archived.")
    elif action == "delete":
        roadmap.delete()
        messages.success(request, "Roadmap deleted.")
        return redirect("learning:roadmaps")
    else:
        messages.warning(request, "That action is not available for this roadmap.")

    return redirect("learning:roadmap_detail", roadmap_id=roadmap.id)
