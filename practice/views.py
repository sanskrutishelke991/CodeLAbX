from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import json
from ai_tools.services import GeminiService


@login_required
def task_list(request):
    """Practice arena home page"""
    return render(request, 'practice/task_list.html')


@login_required
def code_examiner(request):
    """AI Code Examiner page"""
    return render(request, 'practice/code_examiner.html')


@login_required
@require_POST
@csrf_protect
def check_code(request):
    """AI checks user's code and provides feedback with XP + Badges"""
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip()
        language = data.get('language', 'python')
        problem = data.get('problem', '')
        
        if not code:
            return JsonResponse({
                'success': False,
                'error': 'Please write some code first!'
            }, status=400)
        
        # Get AI feedback
        gemini = GeminiService()
        result = gemini.review_code(code, language, problem)
        
        if result['success']:
            response_data = {
                'success': True,
                'feedback': result['feedback_html']
            }
            
            # Award XP and check badges
            try:
                from progress.services import BadgeManager
                
                xp_result = BadgeManager.add_xp(request.user, 15, "Code reviewed")
                new_badges = BadgeManager.check_and_award_badges(request.user)
                
                response_data['xp_earned'] = 15
                response_data['xp_reason'] = 'Code reviewed'
                response_data['leveled_up'] = xp_result.get('leveled_up', False)
                response_data['new_level'] = xp_result.get('new_level')
                response_data['new_badges'] = [
                    {'name': b.badge.name, 'icon': b.badge.icon} 
                    for b in new_badges
                ]
            except Exception as e:
                print(f"Badge/XP error: {e}")
            
            return JsonResponse(response_data)
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Something went wrong')
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
@require_POST
def generate_problem(request):
    """Generate a new practice problem using AI"""
    try:
        data = json.loads(request.body)
        topic = data.get('topic', 'arrays')
        difficulty = data.get('difficulty', 'easy')
        
        gemini = GeminiService()
        result = gemini.generate_practice_problem(topic, difficulty)
        
        if result['success']:
            content = result['content'].strip()
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            try:
                problem_data = json.loads(content)
                return JsonResponse({
                    'success': True,
                    'problem': problem_data
                })
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'AI returned invalid format. Try again.'
                }, status=500)
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error')
            }, status=500)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)