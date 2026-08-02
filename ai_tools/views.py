from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils.html import escape
import json
import logging
from .api import (
    integer_field,
    json_error,
    parse_json_object,
    provider_error_response,
    safe_api_errors,
    text_field,
)
from .rendering import render_ai_markdown
from .security import guard_ai_request, protect_ai_endpoint
from .services import GeminiService
from .models import ChatSession, ChatMessage
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)



@login_required
def ai_home(request):
    """AI Tools home page"""
    return render(request, 'ai_tools/home.html')


@login_required
@require_POST
@csrf_protect
@protect_ai_endpoint(
    "chat",
    "AI_CHAT_BURST_LIMIT",
)
@safe_api_errors
def chat_send(request):
    """Validate and send one AI chat message."""
    data = parse_json_object(request)

    message = text_field(
        data,
        "message",
        required=True,
        min_length=1,
        max_length=settings.AI_CHAT_MAX_CHARS,
    )

    session_id = integer_field(
        data,
        "session_id",
        default=None,
        minimum=1,
    )

    if session_id is not None:
        try:
            session = ChatSession.objects.get(
                id=session_id,
                user=request.user,
            )
        except ChatSession.DoesNotExist:
            return json_error(
                "SESSION_NOT_FOUND",
                (
                    "The requested chat session "
                    "was not found."
                ),
                404,
            )
    else:
        session = ChatSession.objects.create(
            user=request.user,
            title=message[:50],
        )

    ChatMessage.objects.create(
        session=session,
        role="user",
        content=message,
    )

    history = list(
        session.messages
        .order_by("-created_at")
        .values(
            "role",
            "content",
        )[:10]
    )

    history.reverse()

    result = GeminiService().chat(
        message=message,
        chat_history=history[:-1],
        user_context=(
            f"Username: "
            f"{request.user.username}"
        ),
    )

    if not result.get("success"):
        return provider_error_response(
            logger,
            "chat",
            result.get("error"),
        )

    ai_message = ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=result["response_text"],
    )

    return JsonResponse(
        {
            "success": True,
            "session_id": session.id,
            "response": result["response_html"],
            "message_id": ai_message.id,
        }
    )


@login_required
def chat_history(request):
    """Get user's chat sessions"""
    sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')[:20]
    
    data = []
    for session in sessions:
        last_message = session.messages.last()
        data.append({
            'id': session.id,
            'title': session.title,
            'last_message': last_message.content[:100] if last_message else '',
            'updated_at': session.updated_at.strftime('%b %d, %Y %H:%M'),
            'message_count': session.messages.count()
        })
    
    return JsonResponse({
        'success': True,
        'sessions': data
    })


@login_required
def chat_get_session(request, session_id):
    """Get messages from a specific session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        messages = session.messages.all()
        
        data = []
        for msg in messages:
            content_html = escape(msg.content)

            if msg.role == 'assistant':
                content_html = render_ai_markdown(
                    msg.content
                )
            data.append({
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'content_html': content_html,
                'created_at': msg.created_at.strftime('%H:%M')
            })
        
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'title': session.title
            },
            'messages': data
        })
    except ChatSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Session not found'
        }, status=404)


@login_required
@require_POST
def chat_delete_session(request, session_id):
    """Delete a chat session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        session.delete()
        return JsonResponse({'success': True})
    except ChatSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Session not found'
        }, status=404)


@login_required
@require_POST
def chat_new_session(request):
    """Create a new chat session"""
    session = ChatSession.objects.create(
        user=request.user,
        title="New Chat"
    )
    return JsonResponse({
        'success': True,
        'session_id': session.id
    })
@login_required
def image_analyzer(request):
    """Image analyzer page - upload and analyze"""
    from .models import ImageAnalysis
    
    if request.method == 'POST':
        blocked = guard_ai_request(
            request,
            "image-analysis",
            "AI_IMAGE_BURST_LIMIT",
            feature_flag=(
                "IMAGE_ANALYSIS_ENABLED"
            ),
        )

        if blocked is not None:
            return blocked

        image_file = request.FILES.get('image')
        analysis_type = request.POST.get('analysis_type', 'general')
        user_question = request.POST.get('user_question', '').strip()
        
        if not image_file:
            return JsonResponse({
                'success': False,
                'error': 'Please upload an image'
            }, status=400)
        
        # Validate file size (5MB max)
        if image_file.size > 5 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'Image size must be less than 5MB'
            }, status=400)
        
        # Save the analysis record
        analysis = ImageAnalysis.objects.create(
            user=request.user,
            image=image_file,
            analysis_type=analysis_type,
            user_question=user_question
        )
        
        # Analyze with AI
        try:
            gemini = GeminiService()
            result = gemini.analyze_image(
                image_path=analysis.image.path,
                analysis_type=analysis_type,
                user_question=user_question
            )
            
            if result['success']:
                analysis.ai_analysis = result['analysis_html']
                analysis.save()
                
                # Award XP
                try:
                    from progress.services import BadgeManager
                    BadgeManager.add_xp(request.user, 15, "Image analyzed")
                except:
                    pass
                
                return JsonResponse({
                    'success': True,
                    'analysis_id': analysis.id,
                    'analysis_html': result['analysis_html'],
                    'redirect_url': f'/ai-tools/image/{analysis.id}/'
                })
            else:
                analysis.delete()
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'AI analysis failed')
                }, status=500)
        
        except Exception as e:
            analysis.delete()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return render(request, 'ai_tools/image_analyzer.html')


@login_required
def image_result(request, analysis_id):
    """View image analysis result"""
    from .models import ImageAnalysis
    
    analysis = get_object_or_404(ImageAnalysis, id=analysis_id, user=request.user)
    
    return render(request, 'ai_tools/image_result.html', {
        'analysis': analysis
    })


@login_required
def image_history(request):
    """User's image analysis history"""
    from .models import ImageAnalysis
    
    analyses = ImageAnalysis.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'analyses': analyses,
        'total_count': analyses.count(),
    }
    
    return render(request, 'ai_tools/image_history.html', context)


@login_required
@require_POST
def image_delete(request, analysis_id):
    """Delete an image analysis"""
    from .models import ImageAnalysis
    
    analysis = get_object_or_404(ImageAnalysis, id=analysis_id, user=request.user)
    analysis.image.delete(save=False)
    analysis.delete()
    
    return JsonResponse({'success': True})