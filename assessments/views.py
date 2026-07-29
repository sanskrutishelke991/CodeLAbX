from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone
import json
from .models import Test, TestAttempt
from ai_tools.services import GeminiService


@login_required
def quiz_list(request):
    """Display all tests for the current user."""
    status_filter = request.GET.get('status', 'all')
    tests = Test.objects.filter(user=request.user)
    
    if status_filter != 'all':
        tests = tests.filter(status=status_filter)
    
    tests = tests.order_by('-created_at')
    
    return render(request, 'assessments/quiz_list.html', {
        'tests': tests,
        'status_filter': status_filter
    })


@login_required
def create_test(request):
    """Display form to create a new test."""
    return render(request, 'assessments/create_test.html')


@login_required
@require_POST
@csrf_protect
def generate_test_questions(request):
    """API endpoint to generate test questions using AI."""
    try:
        data = json.loads(request.body)
        topic = data.get('topic', '').strip()
        difficulty = data.get('difficulty', 'medium')
        num_questions = data.get('num_questions', 10)
        
        if not topic:
            return JsonResponse({
                'success': False,
                'error': 'Please provide a topic'
            }, status=400)
        
        # Generate questions using Gemini
        gemini = GeminiService()
        result = gemini.generate_test_questions(topic, difficulty, num_questions)
        
        if result['success']:
            try:
                questions = json.loads(result['content'])
                
                # Create test with generated questions
                test = Test.objects.create(
                    user=request.user,
                    title=f"{topic} Quiz ({difficulty})",
                    topic=topic,
                    difficulty=difficulty,
                    num_questions=len(questions),
                    time_limit_minutes=data.get('time_limit', 10),
                    questions=questions,
                    status='created'
                )
                
                return JsonResponse({
                    'success': True,
                    'test_id': test.id,
                    'questions': questions
                })
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'AI returned invalid format. Please try again.'
                }, status=500)
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate questions')
            }, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def take_test(request, test_id):
    """Display test interface with timer and questions."""
    test = get_object_or_404(Test, id=test_id, user=request.user)
    
    # Check if test is already completed
    if test.status == 'completed':
        return redirect('assessments:result', test_id=test.id)
    
    # Update status to in_progress
    if test.status == 'created':
        test.status = 'in_progress'
        test.save()
    
    return render(request, 'assessments/take_test.html', {
        'test': test
    })


@login_required
@require_POST
@csrf_protect
def submit_test(request, test_id):
    """API endpoint to submit test and calculate score."""
    try:
        test = get_object_or_404(Test, id=test_id, user=request.user)
        
        data = json.loads(request.body)
        answers = data.get('answers', {})
        time_taken = data.get('time_taken', 0)
        
        # Calculate score
        correct_count = 0
        total_questions = len(test.questions)
        marks_per_question = test.total_marks / total_questions if total_questions > 0 else 0
        
        for idx, question in enumerate(test.questions):
            user_answer = answers.get(str(idx))
            correct_index = question.get('correct', 0)
            
            if user_answer == correct_index:
                correct_count += 1
        
        score = int(correct_count * marks_per_question)
        
        # Create test attempt
        attempt = TestAttempt.objects.create(
            test=test,
            user=request.user,
            answers=answers,
            score=score,
            time_taken_seconds=time_taken,
            completed_at=timezone.now()
        )
        
        # Update test status and score
        test.status = 'completed'
        test.score = score
        test.completed_at = timezone.now()
        test.save()
        
        return JsonResponse({
            'success': True,
            'score': score,
            'total_marks': test.total_marks,
            'percentage': test.percentage,
            'grade': test.grade,
            'attempt_id': attempt.id
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        # Award XP and check badges
try:
    from progress.services import BadgeManager
    
    # XP based on score percentage
    xp_amount = int(percentage * 2)  # 100% = 200 XP
    xp_result = BadgeManager.add_xp(request.user, xp_amount, "Test completed")
    
    # Check for new badges
    new_badges = BadgeManager.check_and_award_badges(request.user)
    
    # Add to response
    response_data['xp_earned'] = xp_amount
    response_data['xp_reason'] = f'Test scored {percentage}%'
    response_data['leveled_up'] = xp_result.get('leveled_up', False)
    response_data['new_level'] = xp_result.get('new_level')
    response_data['new_badges'] = [
        {'name': b.badge.name, 'icon': b.badge.icon} 
        for b in new_badges
    ]
except Exception as e:
    print(f"Badge/XP error: {e}")

@login_required
def test_result(request, test_id):
    """Display detailed test results."""
    test = get_object_or_404(Test, id=test_id, user=request.user)
    
    # Get the latest attempt
    attempt = test.attempts.filter(user=request.user).order_by('-created_at').first()
    
    if not attempt:
        messages.warning(request, 'No attempt found for this test.')
        return redirect('assessments:quiz_list')
    
    # Prepare question breakdown with user answers
    question_breakdown = []
    for idx, question in enumerate(test.questions):
        user_answer = attempt.answers.get(str(idx))
        correct_index = question.get('correct', 0)
        is_correct = user_answer == correct_index
        
        question_breakdown.append({
            'question': question.get('question'),
            'options': question.get('options', []),
            'user_answer': user_answer,
            'correct_answer': correct_index,
            'is_correct': is_correct,
            'explanation': question.get('explanation', '')
        })
    
    return render(request, 'assessments/test_result.html', {
        'test': test,
        'attempt': attempt,
        'question_breakdown': question_breakdown
    })
