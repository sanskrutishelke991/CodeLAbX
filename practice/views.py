import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from ai_tools.api import (
    APIRequestError,
    choice_field,
    parse_json_object,
    provider_error_response,
    safe_api_errors,
    text_field,
)
from ai_tools.security import protect_ai_endpoint
from ai_tools.services import GeminiService

from .models import CodeReview

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "java",
    "cpp",
    "typescript",
    "go",
    "rust",
    "ruby",
}


@login_required
def task_list(request):
    return render(
        request,
        "practice/task_list.html",
    )


@login_required
def code_examiner(request):
    return render(
        request,
        "practice/code_examiner.html",
    )


def _badge_payload(item):
    badge = getattr(
        item,
        "badge",
        item,
    )

    return {
        "name": badge.name,
        "icon": badge.icon,
    }


@login_required
@require_POST
@csrf_protect
@protect_ai_endpoint(
    "code-review",
    "AI_CODE_REVIEW_BURST_LIMIT",
)
@safe_api_errors
def check_code(request):
    data = parse_json_object(request)

    code = text_field(
        data,
        "code",
        required=True,
        min_length=1,
        max_length=settings.AI_CODE_MAX_CHARS,
    )

    language = choice_field(
        data,
        "language",
        choices=SUPPORTED_LANGUAGES,
        default="python",
    )

    problem = text_field(
        data,
        "problem",
        default="",
        max_length=settings.AI_PROBLEM_MAX_CHARS,
    )

    result = GeminiService().review_code(
        code,
        language,
        problem,
    )

    if not result.get("success"):
        return provider_error_response(
            logger,
            "code-review",
            result.get("error"),
        )

    response_data = {
        "success": True,
        "feedback": result["feedback_html"],
    }

    review_record, review_created = CodeReview.objects.get_or_create(
        user=request.user,
        code_hash=CodeReview.hash_code(language, code),
        defaults={"language": language},
    )

    try:
        from progress.services import BadgeManager

        xp_result = BadgeManager.add_xp(
            request.user,
            15,
            "Code reviewed",
            idempotency_key=f"code-review:{review_record.id}",
            event_type="code-review",
            source_object_type="code-review",
            source_object_id=review_record.id,
        )

        new_badges = (
            BadgeManager.check_and_award_badges(
                request.user
            )
        )

        response_data.update(
            {
                "xp_earned": xp_result["xp_added"],
                "xp_reason": "Code reviewed",
                "leveled_up": xp_result.get(
                    "leveled_up",
                    False,
                ),
                "new_level": xp_result.get(
                    "new_level"
                ),
                "new_badges": [
                    _badge_payload(item)
                    for item in new_badges
                ],
            }
        )

    except Exception:
        logger.warning(
            "XP/badge update failed after code review",
            exc_info=True,
        )

    return JsonResponse(response_data)


@login_required
@require_POST
@protect_ai_endpoint(
    "practice-generation",
    "AI_GENERATION_BURST_LIMIT",
)
@safe_api_errors
def generate_problem(request):
    data = parse_json_object(request)

    topic = text_field(
        data,
        "topic",
        default="arrays",
        min_length=1,
        max_length=settings.AI_TOPIC_MAX_CHARS,
    )

    difficulty = choice_field(
        data,
        "difficulty",
        choices={
            "easy",
            "medium",
            "hard",
        },
        default="easy",
    )

    result = (
        GeminiService()
        .generate_practice_problem(
            topic,
            difficulty,
        )
    )

    if not result.get("success"):
        return provider_error_response(
            logger,
            "practice-generation",
            result.get("error"),
        )

    content = result.get(
        "content",
        "",
    ).strip()

    if content.startswith("```"):
        parts = content.split("```")

        if len(parts) >= 2:
            content = parts[1]

            if content.startswith("json"):
                content = content[4:]

            content = content.strip()

    try:
        problem_data = json.loads(content)

    except json.JSONDecodeError as exc:
        raise APIRequestError(
            "AI_INVALID_RESPONSE",
            (
                "The AI returned an invalid "
                "practice problem."
            ),
            502,
        ) from exc

    if not isinstance(
        problem_data,
        dict,
    ):
        raise APIRequestError(
            "AI_INVALID_RESPONSE",
            (
                "The AI returned an invalid "
                "practice problem."
            ),
            502,
        )

    return JsonResponse(
        {
            "success": True,
            "problem": problem_data,
        }
    )
