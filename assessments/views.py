from datetime import timedelta
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.urls import reverse
import json
import logging
from .models import Test, TestAttempt
from ai_tools.api import (
    APIRequestError,
    choice_field,
    integer_field,
    json_error,
    parse_json_object,
    provider_error_response,
    safe_api_errors,
    text_field,
)
from ai_tools.security import protect_ai_endpoint
from ai_tools.services import GeminiService

logger = logging.getLogger(__name__)


@login_required
def quiz_list(request):
    """Enhanced quiz list with stats and filters"""
    from django.db.models import Avg, Count, Q, Sum
    from .models import Test, TestAttempt
    
    # Get filter params
    status_filter = request.GET.get('status', 'all')
    difficulty_filter = request.GET.get('difficulty', 'all')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'recent')
    view_mode = request.GET.get('view', 'grid')
    
    # Get user tests
    tests = Test.objects.filter(user=request.user)
    
    # Apply filters
    if status_filter != 'all':
        tests = tests.filter(status=status_filter)
    
    if difficulty_filter != 'all':
        tests = tests.filter(difficulty=difficulty_filter)
    
    if search_query:
        tests = tests.filter(
            Q(title__icontains=search_query) | 
            Q(topic__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'recent':
        tests = tests.order_by('-created_at')
    elif sort_by == 'score':
        tests = tests.order_by('-score')
    elif sort_by == 'name':
        tests = tests.order_by('title')
    elif sort_by == 'difficulty':
        tests = tests.order_by('difficulty')
    
    # Calculate stats
    all_tests = Test.objects.filter(user=request.user)
    total_tests = all_tests.count()
    completed_tests = all_tests.filter(status='completed').count()
    in_progress = all_tests.filter(status='in_progress').count()
    created_tests = all_tests.filter(status='created').count()
    
    # Score stats
    completed_qs = all_tests.filter(status='completed')
    if completed_qs.exists():
        avg_score_calc = 0
        total_score_pct = 0
        best_score = 0
        for test in completed_qs:
            if test.total_marks > 0:
                pct = (test.score / test.total_marks) * 100
                total_score_pct += pct
                if pct > best_score:
                    best_score = pct
        avg_score = round(total_score_pct / completed_qs.count(), 1) if completed_qs.count() > 0 else 0
        best_score = round(best_score, 1)
    else:
        avg_score = 0
        best_score = 0
    
    # Difficulty distribution
    easy_count = all_tests.filter(difficulty='easy').count()
    medium_count = all_tests.filter(difficulty='medium').count()
    hard_count = all_tests.filter(difficulty='hard').count()
    
    # Recent completed tests (for performance chart)
    recent_completed = completed_qs.order_by('-completed_at')[:5]
    
    # Time stats
    total_time_seconds = 0
    for test in all_tests:
        if hasattr(test, 'time_limit_minutes') and test.time_limit_minutes:
            total_time_seconds += test.time_limit_minutes * 60
    
    total_hours = round(total_time_seconds / 3600, 1)
    
    page_obj = Paginator(tests, 12).get_page(request.GET.get('page'))

    context = {
        'tests': page_obj,
        'page_obj': page_obj,
        'total_tests': total_tests,
        'completed_tests': completed_tests,
        'in_progress': in_progress,
        'created_tests': created_tests,
        'avg_score': avg_score,
        'best_score': best_score,
        'easy_count': easy_count,
        'medium_count': medium_count,
        'hard_count': hard_count,
        'total_hours': total_hours,
        'recent_completed': recent_completed,
        'status_filter': status_filter,
        'difficulty_filter': difficulty_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'view_mode': view_mode,
    }
    
    return render(request, 'assessments/quiz_list.html', context)



@login_required
def create_test(request):
    """Display form to create a new test."""
    return render(request, 'assessments/create_test.html')



def _validate_generated_questions(value):
    if (
        not isinstance(value, list)
        or not value
        or len(value) > 30
    ):
        raise APIRequestError(
            "AI_INVALID_RESPONSE",
            (
                "The AI returned an invalid "
                "question set."
            ),
            502,
        )

    validated = []

    for item in value:
        if not isinstance(item, dict):
            raise APIRequestError(
                "AI_INVALID_RESPONSE",
                (
                    "The AI returned an invalid "
                    "question set."
                ),
                502,
            )

        question = item.get("question")
        options = item.get("options")
        correct = item.get("correct")
        explanation = item.get(
            "explanation",
            "",
        )

        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > 1000
        ):
            raise APIRequestError(
                "AI_INVALID_RESPONSE",
                (
                    "The AI returned an invalid "
                    "question."
                ),
                502,
            )

        if (
            not isinstance(options, list)
            or not 2 <= len(options) <= 6
        ):
            raise APIRequestError(
                "AI_INVALID_RESPONSE",
                (
                    "The AI returned invalid "
                    "answer options."
                ),
                502,
            )

        if any(
            not isinstance(option, str)
            or not option.strip()
            or len(option) > 500
            for option in options
        ):
            raise APIRequestError(
                "AI_INVALID_RESPONSE",
                (
                    "The AI returned invalid "
                    "answer options."
                ),
                502,
            )

        if (
            isinstance(correct, bool)
            or not isinstance(correct, int)
            or not 0 <= correct < len(options)
        ):
            raise APIRequestError(
                "AI_INVALID_RESPONSE",
                (
                    "The AI returned an invalid "
                    "answer key."
                ),
                502,
            )

        if (
            not isinstance(explanation, str)
            or len(explanation) > 2000
        ):
            raise APIRequestError(
                "AI_INVALID_RESPONSE",
                (
                    "The AI returned an invalid "
                    "explanation."
                ),
                502,
            )

        validated.append(
            {
                "question": question.strip(),
                "options": [
                    option.strip()
                    for option in options
                ],
                "correct": correct,
                "explanation": (
                    explanation.strip()
                ),
            }
        )

    return validated


@login_required
@require_POST
@csrf_protect
@protect_ai_endpoint(
    "test-generation",
    "AI_GENERATION_BURST_LIMIT",
    feature_flag="ASSESSMENTS_ENABLED",
)
@safe_api_errors
def generate_test_questions(request):
    data = parse_json_object(request)

    topic = text_field(
        data,
        "topic",
        required=True,
        min_length=1,
        max_length=min(
            settings.AI_TOPIC_MAX_CHARS,
            150,
        ),
    )

    difficulty = choice_field(
        data,
        "difficulty",
        choices={
            "easy",
            "medium",
            "hard",
        },
        default="medium",
    )

    num_questions = integer_field(
        data,
        "num_questions",
        default=10,
        minimum=1,
        maximum=30,
    )

    time_key = (
        "time_limit_minutes"
        if "time_limit_minutes" in data
        else "time_limit"
    )

    time_limit = integer_field(
        data,
        time_key,
        default=10,
        minimum=1,
        maximum=180,
    )

    result = (
        GeminiService()
        .generate_test_questions(
            topic,
            difficulty,
            num_questions,
        )
    )

    if not result.get("success"):
        return provider_error_response(
            logger,
            "test-generation",
            result.get("error"),
        )

    try:
        generated = json.loads(
            result.get("content", "")
        )

    except json.JSONDecodeError as exc:
        raise APIRequestError(
            "AI_INVALID_RESPONSE",
            (
                "The AI returned an invalid "
                "question set."
            ),
            502,
        ) from exc

    questions = (
        _validate_generated_questions(
            generated
        )
    )

    with transaction.atomic():
        test = Test.objects.create(
            user=request.user,
            title=(
                f"{topic} Quiz ({difficulty})"
            )[:200],
            topic=topic,
            difficulty=difficulty,
            num_questions=len(questions),
            time_limit_minutes=time_limit,
            questions=questions,
            status="created",
        )

    return JsonResponse(
        {
            "success": True,
            "test_id": test.id,
            "redirect_url": reverse(
                "assessments:take",
                args=[test.id],
            ),
        }
    )


@login_required
def take_test(request, test_id):
    """Start or resume one server-timed assessment attempt."""
    test = get_object_or_404(Test, id=test_id, user=request.user)

    attempt = (
        TestAttempt.objects.filter(test=test, user=request.user)
        .order_by("-created_at")
        .first()
    )

    if attempt and (attempt.is_finalized or attempt.completed_at):
        if not attempt.is_finalized:
            attempt.is_finalized = True
            attempt.save(update_fields=["is_finalized"])
        return redirect("assessments:result", test_id=test.id)

    if attempt is None:
        attempt = TestAttempt.objects.create(
            test=test,
            user=request.user,
            deadline_at=timezone.now()
            + timedelta(minutes=test.time_limit_minutes),
        )
    elif attempt.deadline_at is None:
        attempt.deadline_at = attempt.created_at + timedelta(
            minutes=test.time_limit_minutes
        )
        attempt.save(update_fields=["deadline_at"])

    if test.status == "created":
        test.status = "in_progress"
        test.save(update_fields=["status"])

    public_questions = []
    for question in test.questions:
        if not isinstance(question, dict):
            continue
        options = question.get("options", [])
        if not isinstance(options, list):
            options = []
        public_questions.append(
            {
                "question": str(question.get("question", "")),
                "options": [str(option) for option in options],
            }
        )

    remaining = max(
        0,
        int((attempt.deadline_at - timezone.now()).total_seconds()),
    )

    return render(
        request,
        "assessments/take_test.html",
        {
            "test": test,
            "attempt": attempt,
            "seconds_remaining": remaining,
            "public_questions": public_questions,
        },
    )


@login_required
@require_POST
@csrf_protect
@safe_api_errors
@transaction.atomic
def submit_test(request, test_id):
    """Finalize one assessment attempt using server-controlled timing."""
    test = get_object_or_404(
        Test.objects.select_for_update(),
        id=test_id,
        user=request.user,
    )
    data = parse_json_object(request)
    attempt_id = integer_field(
        data,
        "attempt_id",
        required=True,
        minimum=1,
    )
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        raise APIRequestError(
            "VALIDATION_ERROR",
            "answers must be an object.",
            400,
        )

    attempt = get_object_or_404(
        TestAttempt.objects.select_for_update(),
        id=attempt_id,
        test=test,
        user=request.user,
    )

    if attempt.is_finalized or attempt.completed_at:
        return JsonResponse(
            {
                "success": True,
                "already_finalized": True,
                "score": attempt.score or 0,
                "total_marks": test.total_marks,
                "percentage": attempt.percentage,
                "attempt_id": attempt.id,
                "xp_earned": 0,
            }
        )

    now = timezone.now()
    if attempt.deadline_at and now > attempt.deadline_at + timedelta(seconds=30):
        attempt.answers = {}
        attempt.score = 0
        attempt.time_taken_seconds = test.time_limit_minutes * 60
        attempt.completed_at = now
        attempt.is_finalized = True
        attempt.save(
            update_fields=[
                "answers",
                "score",
                "time_taken_seconds",
                "completed_at",
                "is_finalized",
            ]
        )
        test.status = "completed"
        test.score = 0
        test.completed_at = now
        test.save(update_fields=["status", "score", "completed_at"])
        return json_error(
            "TEST_EXPIRED",
            "The assessment deadline has passed.",
            410,
        )

    validated_answers = {}
    for raw_index, raw_answer in answers.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise APIRequestError(
                "VALIDATION_ERROR",
                "An answer index is invalid.",
                400,
            ) from exc
        if index < 0 or index >= len(test.questions):
            raise APIRequestError(
                "VALIDATION_ERROR",
                "An answer index is out of range.",
                400,
            )
        if isinstance(raw_answer, bool) or not isinstance(raw_answer, int):
            raise APIRequestError(
                "VALIDATION_ERROR",
                "An answer value is invalid.",
                400,
            )
        options = test.questions[index].get("options", [])
        if raw_answer < 0 or raw_answer >= len(options):
            raise APIRequestError(
                "VALIDATION_ERROR",
                "An answer value is out of range.",
                400,
            )
        validated_answers[str(index)] = raw_answer

    correct_count = 0
    for index, question in enumerate(test.questions):
        if validated_answers.get(str(index)) == question.get("correct"):
            correct_count += 1

    total_questions = len(test.questions)
    score = (
        round(correct_count * test.total_marks / total_questions)
        if total_questions
        else 0
    )
    elapsed = max(0, int((now - attempt.created_at).total_seconds()))
    elapsed = min(elapsed, test.time_limit_minutes * 60)

    attempt.answers = validated_answers
    attempt.score = score
    attempt.time_taken_seconds = elapsed
    attempt.completed_at = now
    attempt.is_finalized = True
    attempt.save(
        update_fields=[
            "answers",
            "score",
            "time_taken_seconds",
            "completed_at",
            "is_finalized",
        ]
    )

    test.status = "completed"
    test.score = score
    test.completed_at = now
    test.save(update_fields=["status", "score", "completed_at"])

    from progress.services import BadgeManager

    percentage = attempt.percentage
    xp_amount = max(10, round(percentage))
    xp_result = BadgeManager.add_xp(
        request.user,
        xp_amount,
        "Assessment completed",
        idempotency_key=f"assessment-attempt:{attempt.id}",
        event_type="assessment-completed",
        source_object_type="test-attempt",
        source_object_id=attempt.id,
        metadata={"score": score, "percentage": percentage},
    )
    new_badges = BadgeManager.check_and_award_badges(request.user)

    return JsonResponse(
        {
            "success": True,
            "already_finalized": False,
            "score": score,
            "total_marks": test.total_marks,
            "percentage": percentage,
            "grade": test.grade,
            "attempt_id": attempt.id,
            "xp_earned": xp_result["xp_added"],
            "leveled_up": xp_result["leveled_up"],
            "new_level": xp_result["new_level"],
            "new_badges": [
                {
                    "name": getattr(item, "badge", item).name,
                    "icon": getattr(item, "badge", item).icon,
                }
                for item in new_badges
            ],
        }
    )


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
