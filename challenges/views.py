from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from ai_tools.api import (
    APIRequestError,
    integer_field,
    parse_json_object,
    safe_api_errors,
    text_field,
)
from ai_tools.security import guard_ai_request
from ai_tools.services import GeminiService
from intelligence.services.emitters import emit_challenge_attempt
from progress.services import BadgeManager

from .models import Challenge, ChallengeStreak, UserChallenge

logger = logging.getLogger(__name__)


def get_or_create_today_challenges():
    """Read today's pre-generated challenges without calling AI from GET."""
    return Challenge.objects.filter(date=timezone.localdate())


@login_required
def challenge_dashboard(request):
    """Display pre-generated challenges and owner-scoped attempt state."""
    today_challenges = list(get_or_create_today_challenges())
    attempts = {
        attempt.challenge_id: attempt
        for attempt in UserChallenge.objects.filter(
            user=request.user,
            challenge__in=today_challenges,
        )
    }
    challenges_with_status = [
        {
            "challenge": challenge,
            "attempt": attempts.get(challenge.id),
            "completed": (
                attempts.get(challenge.id) is not None
                and attempts[challenge.id].status == "completed"
            ),
        }
        for challenge in today_challenges
    ]

    streak, _ = ChallengeStreak.objects.get_or_create(user=request.user)
    recent_completions = (
        UserChallenge.objects.filter(
            user=request.user,
            status="completed",
        )
        .select_related("challenge")
        .order_by("-completed_at")[:5]
    )
    leaderboard = (
        ChallengeStreak.objects.filter(
            Q(user__profile__is_public=True)
            | Q(user=request.user)
        )
        .select_related("user")
        .order_by("-total_challenges_completed")[:10]
    )

    return render(
        request,
        "challenges/dashboard.html",
        {
            "today": timezone.localdate(),
            "challenges_with_status": challenges_with_status,
            "streak": streak,
            "recent_completions": recent_completions,
            "leaderboard": leaderboard,
        },
    )


@login_required
def challenge_attempt(request, challenge_id):
    """Display one challenge and any existing owner-scoped attempt."""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    attempt = UserChallenge.objects.filter(
        user=request.user,
        challenge=challenge,
    ).first()
    if attempt and attempt.status == "completed":
        return redirect("challenges:result", challenge_id=challenge.id)
    return render(
        request,
        "challenges/attempt.html",
        {"challenge": challenge, "attempt": attempt},
    )


def _completed_payload(challenge, attempt):
    theory = challenge.challenge_type == "theory"
    return {
        "success": True,
        "already_completed": True,
        "is_correct": attempt.is_correct,
        "xp_earned": 0,
        "correct_option": challenge.correct_option if theory else None,
        "explanation": challenge.explanation if theory else None,
        "redirect_url": reverse(
            "challenges:result",
            args=[challenge.id],
        ),
        "evaluation_type": attempt.evaluation_type,
        "ai_feedback": attempt.ai_feedback if not theory else None,
    }


@login_required
@require_POST
@csrf_protect
@safe_api_errors
def challenge_submit(request, challenge_id):
    """Validate and atomically finalize one challenge attempt."""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    completed_attempt = UserChallenge.objects.filter(
        user=request.user,
        challenge=challenge,
        status="completed",
    ).first()
    if completed_attempt:
        return JsonResponse(_completed_payload(challenge, completed_attempt))

    data = parse_json_object(request)
    time_taken = integer_field(
        data,
        "time_taken",
        default=0,
        minimum=0,
        maximum=7 * 24 * 60 * 60,
    )

    code = ""
    selected_option = None
    ai_feedback = ""
    evaluation_type = "deterministic"
    if challenge.challenge_type == "coding":
        code = text_field(
            data,
            "code",
            required=True,
            min_length=1,
            max_length=settings.AI_CODE_MAX_CHARS,
        )
        evaluation_type = "attempt_only"
        if (
            settings.AI_FEATURES_ENABLED
            and settings.CODING_CHALLENGES_ENABLED
        ):
            blocked = guard_ai_request(
                request,
                "challenge-feedback",
                "AI_CODE_REVIEW_BURST_LIMIT",
                feature_flag="CODING_CHALLENGES_ENABLED",
            )
            if blocked is not None:
                return blocked
            try:
                review = GeminiService().review_code(
                    code=code,
                    language="python",
                    problem_statement=challenge.description,
                )
                if review.get("success"):
                    ai_feedback = review.get("feedback_html", "")
                    evaluation_type = "ai_feedback"
                else:
                    logger.warning(
                        "Challenge feedback provider failed: %s",
                        review.get("error", "unknown provider failure"),
                    )
            except Exception:
                logger.exception("Challenge feedback generation failed")
    else:
        options = challenge.options if isinstance(challenge.options, list) else []
        if len(options) < 2:
            raise APIRequestError(
                "CHALLENGE_INVALID",
                "This challenge is not configured correctly.",
                409,
            )
        selected_option = integer_field(
            data,
            "selected_option",
            required=True,
            minimum=0,
            maximum=len(options) - 1,
        )

    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        attempt = UserChallenge.objects.select_for_update().filter(
            user=request.user,
            challenge=challenge,
        ).first()
        if attempt and attempt.status == "completed":
            return JsonResponse(_completed_payload(challenge, attempt))
        if attempt is None:
            attempt = UserChallenge(
                user=request.user,
                challenge=challenge,
            )

        is_correct = (
            selected_option == challenge.correct_option
            if challenge.challenge_type == "theory"
            else False
        )
        planned_xp = (
            challenge.xp_reward
            if is_correct
            else int(challenge.xp_reward * 0.3)
        )

        attempt.user_answer = code
        attempt.selected_option = selected_option
        attempt.time_taken_seconds = time_taken
        attempt.evaluation_type = evaluation_type
        attempt.ai_feedback = ai_feedback
        attempt.is_correct = is_correct
        attempt.status = "completed"
        attempt.completed_at = timezone.now()
        attempt.xp_earned = 0
        attempt.save()

        streak, _ = ChallengeStreak.objects.get_or_create(user=request.user)
        streak.update_streak()

        xp_result = BadgeManager.add_xp(
            request.user,
            planned_xp,
            f"Daily {challenge.challenge_type} challenge",
            idempotency_key=f"challenge:{challenge.id}",
            event_type="challenge-completed",
            source_object_type="challenge",
            source_object_id=challenge.id,
        )
        BadgeManager.check_and_award_badges(request.user)
        awarded_xp = xp_result.get("xp_added", 0)
        attempt.xp_earned = awarded_xp
        attempt.save(update_fields=["xp_earned"])
        emit_challenge_attempt(request.user, attempt)

    theory = challenge.challenge_type == "theory"
    return JsonResponse(
        {
            "success": True,
            "already_completed": False,
            "is_correct": is_correct,
            "xp_earned": awarded_xp,
            "correct_option": challenge.correct_option if theory else None,
            "explanation": challenge.explanation if theory else None,
            "redirect_url": reverse(
                "challenges:result",
                args=[challenge.id],
            ),
            "evaluation_type": attempt.evaluation_type,
            "ai_feedback": attempt.ai_feedback if not theory else None,
        }
    )


@login_required
def challenge_result(request, challenge_id):
    """Show an owner-scoped challenge result."""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    attempt = get_object_or_404(
        UserChallenge,
        user=request.user,
        challenge=challenge,
    )
    return render(
        request,
        "challenges/result.html",
        {"challenge": challenge, "attempt": attempt},
    )


@login_required
def challenge_history(request):
    """Show bounded owner-scoped challenge history and recorded totals."""
    attempts = UserChallenge.objects.filter(
        user=request.user,
    ).select_related("challenge")
    summary = attempts.aggregate(
        completed_count=Count(
            "id",
            filter=Q(status="completed"),
        ),
        correct_count=Count(
            "id",
            filter=Q(is_correct=True),
        ),
        total_xp=Sum("xp_earned"),
    )
    completed_count = summary["completed_count"] or 0
    correct_count = summary["correct_count"] or 0
    streak, _ = ChallengeStreak.objects.get_or_create(user=request.user)

    return render(
        request,
        "challenges/history.html",
        {
            "attempts": attempts.order_by("-completed_at")[:30],
            "completed_count": completed_count,
            "correct_count": correct_count,
            "total_xp": summary["total_xp"] or 0,
            "streak": streak,
            "accuracy": round(
                correct_count / max(completed_count, 1) * 100,
                1,
            ),
        },
    )
