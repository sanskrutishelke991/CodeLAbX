from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from .models import VideoCategory, Video, UserVideoProgress


@login_required
def library(request):
    """Video library home"""
    query = request.GET.get('q', '')
    category_slug = request.GET.get('category', '')
    difficulty = request.GET.get('difficulty', '')
    
    videos = Video.objects.filter(is_active=True).select_related('category')
    
    if query:
        videos = videos.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    
    if category_slug:
        videos = videos.filter(category__slug=category_slug)
    
    if difficulty:
        videos = videos.filter(difficulty=difficulty)
    
    # Get featured videos separately
    featured_videos = Video.objects.filter(is_active=True, is_featured=True).select_related('category')[:6]
    
    # Categories with count
    categories = VideoCategory.objects.annotate(
        video_count=Count('videos', filter=Q(videos__is_active=True))
    )
    
    # User's watched videos
    watched_video_ids = list(UserVideoProgress.objects.filter(
        user=request.user,
        is_watched=True
    ).values_list('video_id', flat=True))
    
    page_obj = Paginator(videos, 12).get_page(request.GET.get('page'))

    context = {
        'videos': page_obj,
        'page_obj': page_obj,
        'featured_videos': featured_videos,
        'categories': categories,
        'query': query,
        'active_category': category_slug,
        'active_difficulty': difficulty,
        'total_videos': Video.objects.filter(is_active=True).count(),
        'watched_video_ids': watched_video_ids,
    }
    
    return render(request, 'content/library.html', context)


@login_required
def video_detail(request, video_id):
    """Video player page"""
    video = get_object_or_404(Video, id=video_id, is_active=True)
    
    # Get or create progress
    progress, created = UserVideoProgress.objects.get_or_create(
        user=request.user,
        video=video
    )
    
    # Increment view count on first view
    if created:
        video.view_count += 1
        video.save()
    
    # Get related videos (same category, exclude current)
    related_videos = Video.objects.filter(
        category=video.category,
        is_active=True
    ).exclude(id=video.id)[:6]
    
    context = {
        'video': video,
        'progress': progress,
        'related_videos': related_videos,
    }
    
    return render(request, 'content/video_detail.html', context)


@login_required
@require_POST
@transaction.atomic
def video_mark_watched(request, video_id):
    """Mark a video watched and award XP once."""
    from progress.services import BadgeManager

    video = get_object_or_404(Video, id=video_id, is_active=True)
    progress, _ = UserVideoProgress.objects.get_or_create(
        user=request.user,
        video=video,
    )
    progress = UserVideoProgress.objects.select_for_update().get(pk=progress.pk)

    if progress.is_watched:
        return JsonResponse(
            {
                "success": True,
                "already_watched": True,
                "xp_earned": 0,
                "message": "Video was already marked as watched.",
            }
        )

    progress.is_watched = True
    progress.completed_at = progress.completed_at or timezone.now()
    progress.save(update_fields=["is_watched", "completed_at", "last_watched_at"])

    xp_result = BadgeManager.add_xp(
        request.user,
        10,
        "Watched video",
        idempotency_key=f"video-watched:{video.id}",
        event_type="video-watched",
        source_object_type="video",
        source_object_id=video.id,
    )

    return JsonResponse(
        {
            "success": True,
            "already_watched": False,
            "xp_earned": xp_result["xp_added"],
            "message": "Video marked as watched!",
        }
    )


@login_required
@require_POST
def video_toggle_favorite(request, video_id):
    """Toggle favorite status"""
    video = get_object_or_404(Video, id=video_id)
    progress, _ = UserVideoProgress.objects.get_or_create(
        user=request.user,
        video=video
    )
    
    progress.is_favorited = not progress.is_favorited
    progress.save()
    
    return JsonResponse({
        'success': True,
        'is_favorited': progress.is_favorited
    })


@login_required
def my_videos(request):
    """User's watched and favorited videos"""
    tab = request.GET.get('tab', 'watched')
    
    if tab == 'favorites':
        progress = UserVideoProgress.objects.filter(
            user=request.user,
            is_favorited=True
        ).select_related('video')
    else:
        progress = UserVideoProgress.objects.filter(
            user=request.user,
            is_watched=True
        ).select_related('video')
    
    context = {
        'progress_list': progress,
        'active_tab': tab,
        'watched_count': UserVideoProgress.objects.filter(user=request.user, is_watched=True).count(),
        'favorites_count': UserVideoProgress.objects.filter(user=request.user, is_favorited=True).count(),
    }
    
    return render(request, 'content/my_videos.html', context)