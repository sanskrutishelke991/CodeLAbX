from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils.html import escape
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Count
import json
import logging
from .api import (
    choice_field,
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
from .uploads import normalize_uploaded_image
from .models import ChatSession, ChatMessage
from django.shortcuts import get_object_or_404
from intelligence.services.tutor_context import build_tutor_context

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

    try:
        tutor_context = build_tutor_context(
            request.user,
            session=session,
        )
        user_context = tutor_context.prompt
    except Exception:
        logger.exception(
            "Tutor context could not be built; continuing without personalization"
        )
        tutor_context = None
        user_context = ""

    result = GeminiService().chat(
        message=message,
        chat_history=history[:-1],
        user_context=user_context,
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
    session.save(update_fields=["updated_at"])

    return JsonResponse(
        {
            "success": True,
            "session_id": session.id,
            "response": result["response_html"],
            "message_id": ai_message.id,
            "personalized": bool(
                tutor_context and tutor_context.personalized
            ),
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
    """Render or securely process image analysis."""
    if request.method == "POST":
        return _process_image_analysis(
            request
        )

    return render(
        request,
        "ai_tools/image_analyzer.html",
    )


@safe_api_errors
def _process_image_analysis(request):
    from .models import ImageAnalysis

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

    values = {
        "analysis_type": request.POST.get(
            "analysis_type",
            "general",
        ),
        "user_question": request.POST.get(
            "user_question",
            "",
        ),
    }

    analysis_type = choice_field(
        values,
        "analysis_type",
        choices={
            "general",
            "code",
            "math",
            "handwritten",
            "diagram",
        },
        default="general",
    )

    user_question = text_field(
        values,
        "user_question",
        default="",
        max_length=(
            settings.AI_IMAGE_QUESTION_MAX_CHARS
        ),
    )

    image_file = request.FILES.get(
        "image"
    )

    if image_file is None:
        return json_error(
            "IMAGE_REQUIRED",
            "Please upload an image.",
            400,
        )

    normalized_image = normalize_uploaded_image(
        image_file
    )

    analysis = ImageAnalysis.objects.create(
        user=request.user,
        image=normalized_image,
        analysis_type=analysis_type,
        user_question=user_question,
    )

    try:
        result = (
            GeminiService()
            .analyze_image(
                image_path=analysis.image.path,
                analysis_type=analysis_type,
                user_question=user_question,
            )
        )

    except Exception:
        analysis.image.delete(
            save=False
        )

        analysis.delete()
        raise

    if not result.get("success"):
        detail = result.get("error")

        analysis.image.delete(
            save=False
        )

        analysis.delete()

        return provider_error_response(
            logger,
            "image-analysis",
            detail,
        )

    analysis.ai_analysis = (
        result["analysis_html"]
    )

    analysis.save(
        update_fields=[
            "ai_analysis"
        ]
    )

    try:
        from progress.services import BadgeManager

        BadgeManager.add_xp(
            request.user,
            15,
            "Image analyzed",
            idempotency_key=f"image-analysis:{analysis.id}",
            event_type="image-analysis",
            source_object_type="image-analysis",
            source_object_id=analysis.id,
        )

    except Exception:
        logger.warning(
            (
                "XP update failed after "
                "image analysis"
            ),
            exc_info=True,
        )

    return JsonResponse(
        {
            "success": True,
            "analysis_id": analysis.id,
            "analysis_html": (
                result["analysis_html"]
            ),
            "redirect_url": reverse(
                "ai_tools:image_result",
                args=[analysis.id],
            ),
        }
    )


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
    
    total_count = analyses.count()
    page_obj = Paginator(analyses, 12).get_page(request.GET.get("page"))
    context = {
        "analyses": page_obj,
        "page_obj": page_obj,
        "total_count": total_count,
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

@login_required
def chat_sessions_page(request):
    """Render an owner-scoped UI for saved chat sessions."""
    sessions = (
        ChatSession.objects.filter(user=request.user)
        .annotate(message_count=Count("messages"))
        .order_by("-updated_at")
    )
    page_obj = Paginator(sessions, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "ai_tools/chat_sessions.html",
        {"sessions": page_obj, "page_obj": page_obj},
    )
