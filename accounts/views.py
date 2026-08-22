import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from assessments.models import Test
from challenges.models import UserChallenge
from content.models import UserVideoProgress
from learning.models import Day, Roadmap
from notes.models import Note
from progress.models import DailyActivity, UserBadge, UserLevel, UserStreak
from intelligence.models import (
    DiagnosticResponse,
    LearnerIntelligenceProfile,
    RoadmapNode,
    RoadmapRevision,
)
from codelabx.throttling import is_rate_limited

from .forms import ProfileUpdateForm, RegistrationForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        if is_rate_limited(
            request,
            "register",
            django_settings.AUTH_REGISTER_ATTEMPTS,
            django_settings.AUTH_REGISTER_WINDOW_SECONDS,
        ):
            form = RegistrationForm(request.POST)
            messages.error(request, "Too many registration attempts. Please try again later.")
            return render(request, 'accounts/register.html', {'form': form}, status=429)

        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('accounts:login')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        if is_rate_limited(
            request,
            "login",
            django_settings.AUTH_LOGIN_ATTEMPTS,
            django_settings.AUTH_LOGIN_WINDOW_SECONDS,
        ):
            messages.error(request, "Too many login attempts. Please try again later.")
            return render(request, 'accounts/login.html', status=429)

        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('dashboard:home')
        messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


def _build_profile_context(request, profile_user, profile_obj):
    """Build one optimized context for private and public profile pages."""
    is_own_profile = request.user.is_authenticated and request.user == profile_user

    # Do not create progress rows merely because an anonymous visitor opened a
    # public profile. Ensure them only on the owner's page.
    if is_own_profile:
        level, _ = UserLevel.objects.get_or_create(user=profile_user)
        streak, _ = UserStreak.objects.get_or_create(user=profile_user)
    else:
        level = UserLevel.objects.filter(user=profile_user).first()
        streak = UserStreak.objects.filter(user=profile_user).first()

    recent_badges = list(
        UserBadge.objects.filter(user=profile_user)
        .select_related('badge')
        .order_by('-earned_at')[:6]
    )
    total_badges = UserBadge.objects.filter(user=profile_user).count()

    active_roadmaps = list(
        Roadmap.objects.filter(user=profile_user, status='active')
        .annotate(
            profile_completed_days=Count(
                'days',
                filter=Q(days__is_completed=True),
                distinct=True,
            )
        )
        .order_by('-updated_at')[:3]
    )
    for roadmap in active_roadmaps:
        roadmap.profile_progress = (
            round((roadmap.profile_completed_days / roadmap.total_days) * 100, 1)
            if roadmap.total_days
            else 0
        )
        roadmap.profile_remaining_days = max(
            roadmap.total_days - roadmap.profile_completed_days,
            0,
        )

    completed_days = Day.objects.filter(
        roadmap__user=profile_user,
        is_completed=True,
    ).count()
    total_minutes = (
        DailyActivity.objects.filter(user=profile_user).aggregate(
            total=Sum('minutes_studied')
        )['total']
        or 0
    )

    stats = {
        'days_completed': completed_days,
        'hours_studied': round(total_minutes / 60, 1),
        'tests_completed': Test.objects.filter(
            user=profile_user,
            status='completed',
        ).count(),
        'challenges_completed': UserChallenge.objects.filter(
            user=profile_user,
            status='completed',
        ).count(),
        'videos_watched': UserVideoProgress.objects.filter(
            user=profile_user,
            is_watched=True,
        ).count(),
        'notes_created': Note.objects.filter(user=profile_user).count(),
        'active_roadmaps': Roadmap.objects.filter(
            user=profile_user,
            status='active',
        ).count(),
        'completed_roadmaps': Roadmap.objects.filter(
            user=profile_user,
            status='completed',
        ).count(),
    }

    # Six meaningful profile-completion groups.
    completion_parts = [
        bool(profile_obj.avatar),
        bool(profile_obj.bio.strip()),
        bool(profile_obj.location.strip()),
        bool(profile_obj.skills),
        bool(profile_obj.learning_goals.strip()),
        any(
            [
                profile_obj.github_url,
                profile_obj.linkedin_url,
                profile_obj.twitter_url,
                profile_obj.website_url,
            ]
        ),
    ]
    profile_completion = round(
        (sum(completion_parts) / len(completion_parts)) * 100
    )

    level_number = level.current_level if level else 1
    current_xp = level.current_xp if level else 0
    total_xp = level.total_xp_earned if level else 0
    next_level_xp = level.xp_for_next_level() if level else 100
    xp_to_next_level = max(next_level_xp - current_xp, 0)
    level_progress = level.level_progress_percentage() if level else 0
    current_streak = streak.current_streak if streak else 0
    longest_streak = streak.longest_streak if streak else 0

    return {
        'profile_user': profile_user,
        'profile': profile_obj,
        'is_own_profile': is_own_profile,
        'level': level,
        'streak': streak,
        'level_number': level_number,
        'current_xp': current_xp,
        'total_xp': total_xp,
        'next_level_xp': next_level_xp,
        'xp_to_next_level': xp_to_next_level,
        'level_progress': level_progress,
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'recent_badges': recent_badges,
        'total_badges': total_badges,
        'active_roadmaps': active_roadmaps,
        'stats': stats,
        'profile_completion': profile_completion,
        'profile_url': request.build_absolute_uri(
            reverse('accounts:public_profile', args=[profile_user.username])
        ),
    }


@login_required
def profile(request):
    """Display the signed-in user's profile."""
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        'accounts/profile.html',
        _build_profile_context(request, request.user, profile_obj),
    )


@login_required
def profile_edit(request):
    """Edit the signed-in user's profile."""
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=profile_obj)

    return render(
        request,
        'accounts/profile_edit.html',
        {'form': form, 'profile': profile_obj},
    )


def public_profile(request, username):
    """Display a public user profile."""
    profile_user = get_object_or_404(User, username=username)
    profile_obj, _ = UserProfile.objects.get_or_create(user=profile_user)

    if not profile_obj.is_public and profile_user != request.user:
        messages.warning(request, 'This profile is private.')
        return redirect('dashboard:home')

    return render(
        request,
        'accounts/profile.html',
        _build_profile_context(request, profile_user, profile_obj),
    )


@login_required
def settings(request):
    return render(request, 'accounts/settings.html')


def _export_learning_intelligence(user):
    intelligence_profile = (
        LearnerIntelligenceProfile.objects.filter(user=user)
        .values(
            "primary_goal",
            "custom_goal",
            "selected_pack__code",
            "selected_pack__version",
            "routing_diagnostic_completed_at",
            "goal_diagnostic_completed_at",
            "created_at",
            "updated_at",
        )
        .first()
    )
    missions = list(
        user.intelligence_missions.select_related("primary_skill")
        .prefetch_related("additional_skills")
        .order_by("created_at")
    )
    return {
        "profile": intelligence_profile,
        "learning_events": list(
            user.learning_events.values(
                "skill__code",
                "event_type",
                "source_type",
                "outcome",
                "difficulty",
                "evidence_weight",
                "hints_used",
                "retry_count",
                "duration_seconds",
                "metadata",
                "occurred_at",
                "schema_version",
            )
        ),
        "skill_states": list(
            user.skill_states.values(
                "skill__code",
                "mastery",
                "confidence",
                "freshness",
                "evidence_count",
                "total_evidence_weight",
                "last_evidence_at",
                "misconception_codes",
                "algorithm_version",
                "calculated_at",
            )
        ),
        "diagnostic_attempts": list(
            user.diagnostic_attempts.values(
                "stage",
                "diagnostic_code",
                "question_set_version",
                "status",
                "score",
                "question_count",
                "started_at",
                "completed_at",
            )
        ),
        "diagnostic_responses": list(
            DiagnosticResponse.objects.filter(attempt__user=user).values(
                "attempt__diagnostic_code",
                "question_id",
                "skill__code",
                "selected_option",
                "is_correct",
                "answered_at",
            )
        ),
        "missions": [
            {
                "primary_skill": mission.primary_skill.code,
                "additional_skills": [
                    skill.code for skill in mission.additional_skills.all()
                ],
                "mission_type": mission.mission_type,
                "status": mission.status,
                "title": mission.title,
                "description": mission.description,
                "rationale": mission.rationale,
                "success_criteria": mission.success_criteria,
                "expected_minutes": mission.expected_minutes,
                "evidence_policy_version": mission.evidence_policy_version,
                "created_at": mission.created_at,
                "updated_at": mission.updated_at,
                "decided_at": mission.decided_at,
                "postponed_until": mission.postponed_until,
            }
            for mission in missions
        ],
        "roadmap_revisions": list(
            RoadmapRevision.objects.filter(roadmap__user=user).values(
                "roadmap__title",
                "revision_number",
                "status",
                "reason_code",
                "summary",
                "input_state_at",
                "algorithm_version",
                "based_on__revision_number",
                "trigger_mission__title",
                "created_at",
                "decided_at",
                "postponed_until",
            )
        ),
        "roadmap_nodes": list(
            RoadmapNode.objects.filter(revision__roadmap__user=user).values(
                "revision__roadmap__title",
                "revision__revision_number",
                "skill__code",
                "mission__title",
                "order",
                "status",
                "rationale",
                "expected_minutes",
                "is_user_locked",
                "created_at",
                "updated_at",
            )
        ),
    }


@login_required
@require_POST
def export_account_data(request):
    """Download a privacy-safe JSON export of the current user's data."""
    user = request.user
    profile = user.profile

    payload = {
        "exported_at": timezone.now(),
        "account": {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
        },
        "profile": {
            "bio": profile.bio,
            "location": profile.location,
            "skills": profile.skills,
            "learning_goals": profile.learning_goals,
            "is_public": profile.is_public,
            "github_url": profile.github_url,
            "linkedin_url": profile.linkedin_url,
            "twitter_url": profile.twitter_url,
            "website_url": profile.website_url,
            "avatar_file": profile.avatar.name if profile.avatar else None,
        },
        "roadmaps": list(user.roadmaps.values()),
        "days": list(Day.objects.filter(roadmap__user=user).values()),
        "tests": list(user.tests.values()),
        "test_attempts": list(user.test_attempts.values()),
        "notes": list(user.notes.values()),
        "bookmarks": list(user.bookmarks.values()),
        "video_progress": list(user.video_progress.values()),
        "challenge_attempts": list(user.challenge_attempts.values()),
        "xp_transactions": list(user.xp_transactions.values()),
        "badges": list(user.badges.values()),
        "chat_sessions": list(user.chat_sessions.values()),
        "image_analyses": list(
            user.image_analyses.values(
                "id",
                "analysis_type",
                "user_question",
                "created_at",
            )
        ),
        "learning_intelligence": _export_learning_intelligence(user),
    }

    response = HttpResponse(
        json.dumps(payload, cls=DjangoJSONEncoder, indent=2),
        content_type="application/json",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="codelabx-{user.username}-export.json"'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def delete_account(request):
    """Delete the authenticated account after password and username confirmation."""
    user = request.user
    confirmation = request.POST.get("confirmation", "").strip()
    password = request.POST.get("password", "")

    if confirmation != user.username or not user.check_password(password):
        messages.error(
            request,
            "Account deletion was not confirmed. Check your username and password.",
        )
        return redirect("accounts:settings")

    if user.profile.avatar:
        user.profile.avatar.delete(save=False)
    for analysis in user.image_analyses.all():
        analysis.image.delete(save=False)

    username = user.username
    logout(request)
    user.delete()
    messages.success(request, f"Account {username} and its data were deleted.")
    return redirect("landing")
