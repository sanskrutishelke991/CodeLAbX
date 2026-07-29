from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Roadmap, Day
from .forms import RoadmapCreateForm
from .services import RoadmapGenerator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from ai_tools.services import GeminiService


@login_required
def roadmap_list(request):
    """Display all roadmaps for the current user."""
    roadmaps = Roadmap.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'learning/roadmap_list.html', {'roadmaps': roadmaps})


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
                    BadgeManager.add_xp(request.user, 25, "Created roadmap")
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
def generate_day_content(request, roadmap_id, day_number):
    """Generate AI theory content for a day"""
    roadmap = get_object_or_404(Roadmap, id=roadmap_id, user=request.user)
    day = get_object_or_404(Day, roadmap=roadmap, day_number=day_number)
    
    try:
        gemini = GeminiService()
        result = gemini.generate_theory(day.title, level=roadmap.level)
        
        if result['success']:
            day.ai_content = result['content_html']
            day.ai_content_generated_at = timezone.now()
            day.save()
            
            return JsonResponse({
                'success': True,
                'content': result['content_html']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }, status=500)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def mark_day_complete(request, roadmap_id, day_number):
    """Mark a day as complete and log activity with XP + Badges"""
    from progress.services import ActivityLogger
    
    roadmap = get_object_or_404(Roadmap, id=roadmap_id, user=request.user)
    day = get_object_or_404(Day, roadmap=roadmap, day_number=day_number)
    
    # Mark as completed
    day.mark_completed()
    
    # Log activity + update streak
    ActivityLogger.log_day_completion(request.user, day)
    
    # Prepare response
    response_data = {
        'success': True,
        'message': f'Day {day.day_number} marked as complete!'
    }
    
    # Award XP and check badges
    try:
        from progress.services import BadgeManager
        
        # Add XP for completing day
        xp_result = BadgeManager.add_xp(request.user, 20, "Completed a day")
        
        # Check for new badges
        new_badges = BadgeManager.check_and_award_badges(request.user)
        
        response_data['xp_earned'] = 20
        response_data['xp_reason'] = 'Day completed'
        response_data['leveled_up'] = xp_result.get('leveled_up', False)
        response_data['new_level'] = xp_result.get('new_level')
        response_data['new_badges'] = [
            {'name': b.badge.name, 'icon': b.badge.icon} 
            for b in new_badges
        ]
    except Exception as e:
        print(f"Badge/XP error: {e}")
    
    return JsonResponse(response_data)