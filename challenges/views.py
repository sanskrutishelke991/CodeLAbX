from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
import json
from datetime import timedelta
from .models import Challenge, UserChallenge, ChallengeStreak


def get_or_create_today_challenges():
    """Get today's challenges, generate if not exist"""
    from ai_tools.services import GeminiService
    
    today = timezone.now().date()
    challenges = Challenge.objects.filter(date=today)
    
    # If both today's challenges exist, return them
    if challenges.count() >= 2:
        return challenges
    
    # Generate missing challenges
    types_needed = ['coding', 'theory']
    existing_types = [c.challenge_type for c in challenges]
    
    for ctype in types_needed:
        if ctype not in existing_types:
            try:
                gemini = GeminiService()
                result = gemini.generate_daily_challenge(
                    challenge_type=ctype,
                    difficulty='medium'
                )
                
                if result['success']:
                    data = result['data']
                    
                    challenge_data = {
                        'date': today,
                        'challenge_type': ctype,
                        'title': data.get('title', 'Daily Challenge'),
                        'description': data.get('description', ''),
                        'difficulty': data.get('difficulty', 'medium'),
                        'xp_reward': 30 if ctype == 'coding' else 15,
                    }
                    
                    if ctype == 'coding':
                        challenge_data.update({
                            'starter_code': data.get('starter_code', ''),
                            'example_input': data.get('example_input', ''),
                            'example_output': data.get('example_output', ''),
                            'hints': data.get('hints', []),
                        })
                    else:
                        challenge_data.update({
                            'options': data.get('options', []),
                            'correct_option': data.get('correct_option', 0),
                            'explanation': data.get('explanation', ''),
                        })
                    
                    Challenge.objects.create(**challenge_data)
            except Exception as e:
                print(f"Error generating {ctype} challenge: {e}")
    
    return Challenge.objects.filter(date=today)


@login_required
def challenge_dashboard(request):
    """Daily challenges dashboard"""
    try:
        today_challenges = get_or_create_today_challenges()
    except Exception as e:
        today_challenges = Challenge.objects.filter(date=timezone.now().date())
    
    # Get user's attempts for today
    user_attempts = UserChallenge.objects.filter(
        user=request.user,
        challenge__in=today_challenges
    )
    
    # Map challenges to attempts
    challenges_with_status = []
    for challenge in today_challenges:
        attempt = user_attempts.filter(challenge=challenge).first()
        challenges_with_status.append({
            'challenge': challenge,
            'attempt': attempt,
            'completed': attempt is not None and attempt.status == 'completed',
        })
    
    # Get streak
    streak, _ = ChallengeStreak.objects.get_or_create(user=request.user)
    
    # Get recent completed challenges
    recent_completions = UserChallenge.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('challenge').order_by('-completed_at')[:5]
    
    # Get leaderboard (top 10 by total challenges)
    leaderboard = ChallengeStreak.objects.select_related('user').order_by('-total_challenges_completed')[:10]
    
    context = {
        'today': timezone.now().date(),
        'challenges_with_status': challenges_with_status,
        'streak': streak,
        'recent_completions': recent_completions,
        'leaderboard': leaderboard,
    }
    
    return render(request, 'challenges/dashboard.html', context)


@login_required
def challenge_attempt(request, challenge_id):
    """Attempt a challenge"""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    
    # Check if already attempted
    attempt = UserChallenge.objects.filter(
        user=request.user,
        challenge=challenge
    ).first()
    
    if attempt and attempt.status == 'completed':
        return redirect('challenges:result', challenge_id=challenge.id)
    
    return render(request, 'challenges/attempt.html', {
        'challenge': challenge,
        'attempt': attempt,
    })


@login_required
@require_POST
@csrf_protect
def challenge_submit(request, challenge_id):
    """Submit challenge answer"""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    
    try:
        data = json.loads(request.body)
        
        # Get or create attempt
        attempt, created = UserChallenge.objects.get_or_create(
            user=request.user,
            challenge=challenge,
            defaults={'status': 'pending'}
        )
        
        is_correct = False
        
        if challenge.challenge_type == 'coding':
            # For coding, save code and mark as completed (we won't actually run code)
            attempt.user_answer = data.get('code', '')
            attempt.time_taken_seconds = data.get('time_taken', 0)
            
            # Use AI to check if code looks correct
            from ai_tools.services import GeminiService
            try:
                gemini = GeminiService()
                review = gemini.review_code(
                    code=attempt.user_answer,
                    language='python',
                    problem_statement=challenge.description
                )
                # If code seems okay, mark correct (simple heuristic)
                if review['success'] and 'correct' in review['feedback_html'].lower():
                    is_correct = True
            except:
                is_correct = True  # Give benefit of doubt
        
        else:  # theory
            selected = data.get('selected_option', -1)
            attempt.selected_option = selected
            is_correct = (selected == challenge.correct_option)
        
        attempt.is_correct = is_correct
        attempt.status = 'completed'
        attempt.completed_at = timezone.now()
        
        # Calculate XP
        if is_correct:
            xp_earned = challenge.xp_reward
            # Bonus for speed on coding
            if challenge.challenge_type == 'coding' and attempt.time_taken_seconds < 300:
                xp_earned += 10
        else:
            xp_earned = int(challenge.xp_reward * 0.3)  # 30% for attempt
        
        attempt.xp_earned = xp_earned
        attempt.save()
        
        # Update streak
        streak, _ = ChallengeStreak.objects.get_or_create(user=request.user)
        streak.update_streak()
        
        # Award XP via progress system
        try:
            from progress.services import BadgeManager
            BadgeManager.add_xp(request.user, xp_earned, f"Daily {challenge.challenge_type} challenge")
            new_badges = BadgeManager.check_and_award_badges(request.user)
        except:
            new_badges = []
        
        return JsonResponse({
            'success': True,
            'is_correct': is_correct,
            'xp_earned': xp_earned,
            'correct_option': challenge.correct_option if challenge.challenge_type == 'theory' else None,
            'explanation': challenge.explanation if challenge.challenge_type == 'theory' else None,
            'redirect_url': f'/challenges/result/{challenge.id}/'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def challenge_result(request, challenge_id):
    """Show challenge result"""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    attempt = get_object_or_404(UserChallenge, user=request.user, challenge=challenge)
    
    return render(request, 'challenges/result.html', {
        'challenge': challenge,
        'attempt': attempt,
    })


@login_required
def challenge_history(request):
    """Show user's challenge history"""
    attempts = UserChallenge.objects.filter(
        user=request.user
    ).select_related('challenge').order_by('-completed_at')
    
    completed_count = attempts.filter(status='completed').count()
    correct_count = attempts.filter(is_correct=True).count()
    total_xp = sum(a.xp_earned for a in attempts)
    
    streak, _ = ChallengeStreak.objects.get_or_create(user=request.user)
    
    context = {
        'attempts': attempts[:30],
        'completed_count': completed_count,
        'correct_count': correct_count,
        'total_xp': total_xp,
        'streak': streak,
        'accuracy': round((correct_count / max(completed_count, 1)) * 100, 1),
    }
    
    return render(request, 'challenges/history.html', context)