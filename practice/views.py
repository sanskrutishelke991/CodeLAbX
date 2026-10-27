import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
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
from ai_tools.services import (
    GeminiService,
    parse_json_object_response,
)
from progress.services import BadgeManager

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


def _generated_text(data, key, maximum, required=True):
    value = data.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{key} is required.")
    if len(value) > maximum:
        raise ValueError(f"{key} is too long.")
    return value


def validate_practice_problem(data, difficulty):
    """Normalize one generated problem before returning it to the browser."""
    hints = data.get("hints", [])
    if not isinstance(hints, list) or len(hints) > 5:
        raise ValueError("hints must be a list of at most five items.")
    normalized_hints = []
    for hint in hints:
        if not isinstance(hint, str) or not hint.strip() or len(hint) > 500:
            raise ValueError("each hint must be bounded text.")
        normalized_hints.append(hint.strip())

    return {
        "title": _generated_text(data, "title", 200),
        "description": _generated_text(data, "description", 5000),
        "input_format": _generated_text(
            data,
            "input_format",
            2000,
            required=False,
        ),
        "output_format": _generated_text(
            data,
            "output_format",
            2000,
            required=False,
        ),
        "constraints": _generated_text(
            data,
            "constraints",
            2000,
            required=False,
        ),
        "example_input": _generated_text(
            data,
            "example_input",
            5000,
            required=False,
        ),
        "example_output": _generated_text(
            data,
            "example_output",
            5000,
            required=False,
        ),
        "explanation": _generated_text(
            data,
            "explanation",
            5000,
            required=False,
        ),
        "hints": normalized_hints,
        "starter_code_python": _generated_text(
            data,
            "starter_code_python",
            20_000,
            required=False,
        ),
        "difficulty": difficulty,
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

    with transaction.atomic():
        review_record, _ = CodeReview.objects.get_or_create(
            user=request.user,
            code_hash=CodeReview.hash_code(language, code),
            defaults={"language": language},
        )
        xp_result = BadgeManager.add_xp(
            request.user,
            15,
            "Code reviewed",
            idempotency_key=f"code-review:{review_record.id}",
            event_type="code-review",
            source_object_type="code-review",
            source_object_id=review_record.id,
        )
        new_badges = BadgeManager.check_and_award_badges(request.user)

    return JsonResponse(
        {
            "success": True,
            "feedback": result["feedback_html"],
            "xp_earned": xp_result["xp_added"],
            "xp_reason": "Code reviewed",
            "leveled_up": xp_result.get("leveled_up", False),
            "new_level": xp_result.get("new_level"),
            "new_badges": [
                _badge_payload(item)
                for item in new_badges
            ],
        }
    )


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

    try:
        problem_data = parse_json_object_response(
            result.get("content", "")
        )
        problem_data = validate_practice_problem(
            problem_data,
            difficulty,
        )
    except ValueError as exc:
        raise APIRequestError(
            "AI_INVALID_RESPONSE",
            "The AI returned an invalid practice problem.",
            502,
        ) from exc

    return JsonResponse(
        {"success": True, "problem": problem_data}
    )
