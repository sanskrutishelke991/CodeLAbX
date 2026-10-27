import json
import logging

from django.core.exceptions import ValidationError
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
from community.models import (
    CommunityReport,
    DayComment,
    DiscussionPost,
    DiscussionThread,
    GroupMembership,
    GroupRoadmapShare,
    StudyGroup,
    UserBlock,
)
from content.models import UserVideoProgress
from learning.models import Day, Roadmap
from notes.models import Note
from progress.models import DailyActivity, UserBadge, UserLevel, UserStreak
from intelligence.models import (
    DiagnosticResponse,
    LearnerIntelligenceProfile,
    PublicShare,
    RoadmapNode,
    RoadmapRevision,
    TutorFeedback,
    TutorMemory,
    TutorPreference,
)
from codelabx.throttling import is_rate_limited

from .forms import (
    EmailPreferenceForm,
    GitHubConnectionForm,
    ProfileUpdateForm,
    RegistrationForm,
)
from .models import (
    EmailPreference,
    GitHubConnection,
    GitHubRepository,
    UserProfile,
    WeeklyReportDelivery,
)
from .services.github_public import (
    GitHubPublicAPIError,
    record_sync_failure,
    sync_public_github,
)
from .services.weekly_reports import (
    render_weekly_report,
    send_weekly_report_preview,
)

logger = logging.getLogger(__name__)


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
    email_preference = EmailPreference.objects.filter(user=request.user).first()
    github_connection = GitHubConnection.objects.filter(user=request.user).first()
    return render(
        request,
        "accounts/settings.html",
        {
            "email_preference": email_preference,
            "github_connection": github_connection,
        },
    )


@login_required
def email_preferences(request):
    preference = EmailPreference.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = EmailPreferenceForm(
            request.POST,
            instance=preference,
            user=request.user,
        )
        if form.is_valid():
            preference = form.save()
            messages.success(
                request,
                "Email report preferences saved."
                if preference.weekly_report_enabled
                else "Weekly report email remains off.",
            )
            return redirect("accounts:email_preferences")
    else:
        form = EmailPreferenceForm(instance=preference, user=request.user)

    backend = django_settings.EMAIL_BACKEND.lower()
    external_delivery_configured = not any(
        marker in backend
        for marker in ("console", "locmem", "dummy", "filebased")
    )
    deliveries = WeeklyReportDelivery.objects.filter(
        user=request.user
    ).order_by("-period_end")[:10]
    return render(
        request,
        "accounts/email_preferences.html",
        {
            "form": form,
            "preference": preference,
            "deliveries": deliveries,
            "external_delivery_configured": external_delivery_configured,
        },
    )


@login_required
def weekly_report_preview(request):
    preference = (
        EmailPreference.objects.filter(user=request.user).first()
        or EmailPreference(user=request.user)
    )
    rendered = render_weekly_report(request.user, preference)
    return render(
        request,
        "accounts/weekly_report_preview.html",
        {
            "preference": preference,
            "report": rendered.data,
            "subject": rendered.subject,
        },
    )


@login_required
@require_POST
def send_weekly_report_test(request):
    if is_rate_limited(
        request,
        f"weekly-report-preview:{request.user.id}",
        django_settings.EMAIL_PREVIEW_ATTEMPTS,
        django_settings.EMAIL_PREVIEW_WINDOW_SECONDS,
    ):
        messages.error(
            request,
            "Too many preview-email requests. Try again later.",
        )
        return redirect("accounts:weekly_report_preview")
    preference = (
        EmailPreference.objects.filter(user=request.user).first()
        or EmailPreference(user=request.user)
    )
    try:
        send_weekly_report_preview(request.user, preference)
    except ValidationError:
        messages.error(
            request,
            "A valid account email is required before a preview can be sent.",
        )
    except Exception:
        logger.exception(
            "Weekly report preview email failed",
            extra={"user_id": request.user.id},
        )
        messages.error(
            request,
            "The configured email backend could not send the preview.",
        )
    else:
        backend = django_settings.EMAIL_BACKEND.lower()
        if any(
            marker in backend
            for marker in ("console", "locmem", "dummy", "filebased")
        ):
            messages.success(
                request,
                "Preview passed to the configured development backend; no external inbox delivery is claimed.",
            )
        else:
            messages.success(
                request,
                "Weekly report preview sent to your account email.",
            )
    return redirect("accounts:weekly_report_preview")


@login_required
def github_portfolio(request):
    connection = (
        GitHubConnection.objects.filter(user=request.user)
        .prefetch_related("repositories")
        .first()
    )
    form = GitHubConnectionForm(
        instance=connection,
        user=request.user,
    )
    repositories = (
        list(connection.repositories.all()[:30]) if connection else []
    )
    return render(
        request,
        "accounts/github_portfolio.html",
        {
            "connection": connection,
            "repositories": repositories,
            "form": form,
            "integration_enabled": (
                django_settings.GITHUB_PUBLIC_INTEGRATION_ENABLED
            ),
        },
    )


def _sync_github_for_request(request, username):
    if is_rate_limited(
        request,
        f"github-refresh:{request.user.id}",
        django_settings.GITHUB_REFRESH_ATTEMPTS,
        django_settings.GITHUB_REFRESH_WINDOW_SECONDS,
    ):
        messages.error(request, "Too many GitHub refresh attempts. Try again later.")
        return
    try:
        result = sync_public_github(request.user, username)
    except GitHubPublicAPIError as exc:
        record_sync_failure(request.user, username, exc.code)
        messages.error(request, exc.public_message)
    except ValidationError:
        messages.error(request, "Enter a valid public GitHub username.")
    except Exception:
        logger.exception(
            "Unexpected GitHub public portfolio refresh failure",
            extra={"user_id": request.user.id},
        )
        record_sync_failure(request.user, username, "github_internal_error")
        messages.error(
            request,
            "GitHub public data could not be refreshed right now.",
        )
    else:
        messages.success(
            request,
            f"Public GitHub portfolio refreshed with {result.repository_count} repositories.",
        )


@login_required
@require_POST
def github_connect(request):
    connection = GitHubConnection.objects.filter(user=request.user).first()
    form = GitHubConnectionForm(
        request.POST,
        instance=connection,
        user=request.user,
    )
    if not form.is_valid():
        messages.error(request, "Enter a valid public GitHub username.")
        return redirect("accounts:github_portfolio")
    _sync_github_for_request(request, form.cleaned_data["username"])
    return redirect("accounts:github_portfolio")


@login_required
@require_POST
def github_refresh(request):
    connection = GitHubConnection.objects.filter(user=request.user).first()
    if connection is None:
        messages.error(request, "Connect a public GitHub username first.")
    else:
        _sync_github_for_request(request, connection.username)
    return redirect("accounts:github_portfolio")


@login_required
@require_POST
def github_disconnect(request):
    connection = GitHubConnection.objects.filter(user=request.user).first()
    if connection:
        connection.delete()
        messages.success(request, "GitHub public portfolio disconnected and cached repositories deleted.")
    return redirect("accounts:github_portfolio")


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
        "public_shares": list(
            PublicShare.objects.filter(user=user).values(
                "share_type",
                "roadmap__title",
                "public_id",
                "display_name",
                "include_evidence_counts",
                "include_completed_items",
                "snapshot",
                "snapshot_hash",
                "snapshot_version",
                "is_active",
                "created_at",
                "refreshed_at",
                "revoked_at",
            )
        ),
        "tutor_preference": (
            TutorPreference.objects.filter(user=user)
            .values(
                "explanation_depth",
                "teaching_mode",
                "code_density",
                "preferred_language",
                "pace",
                "session_minutes",
                "accessibility_preferences",
                "learning_context_enabled",
                "observed_adaptation_enabled",
                "onboarding_completed_at",
                "created_at",
                "updated_at",
            )
            .first()
        ),
        "tutor_memories": list(
            TutorMemory.objects.filter(user=user).values(
                "category",
                "content",
                "reason",
                "source_type",
                "chat_session__title",
                "is_active",
                "user_confirmed",
                "created_at",
                "updated_at",
            )
        ),
        "tutor_feedback": list(
            TutorFeedback.objects.filter(user=user).values(
                "message_id",
                "message__session__title",
                "feedback_type",
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
        "email_preference": (
            EmailPreference.objects.filter(user=user)
            .values(
                "weekly_report_enabled",
                "report_weekday",
                "include_activity",
                "include_skill_progress",
                "include_next_steps",
                "created_at",
                "updated_at",
            )
            .first()
        ),
        "weekly_report_deliveries": list(
            WeeklyReportDelivery.objects.filter(user=user).values(
                "period_start",
                "period_end",
                "status",
                "subject",
                "attempt_count",
                "last_attempt_at",
                "sent_at",
                "created_at",
                "updated_at",
            )
        ),
        "github_public_connection": (
            GitHubConnection.objects.filter(user=user)
            .values(
                "username",
                "github_user_id",
                "profile_url",
                "display_name",
                "bio",
                "public_repos",
                "followers",
                "status",
                "fetched_at",
                "created_at",
                "updated_at",
            )
            .first()
        ),
        "github_public_repositories": list(
            GitHubRepository.objects.filter(connection__user=user).values(
                "github_id",
                "name",
                "full_name",
                "html_url",
                "description",
                "language",
                "stargazers_count",
                "forks_count",
                "is_fork",
                "pushed_at",
                "fetched_at",
            )
        ),
        "community": {
            "owned_groups": list(
                StudyGroup.objects.filter(owner=user).values(
                    "id", "name", "description", "max_members", "is_active",
                    "created_at", "updated_at",
                )
            ),
            "memberships": list(
                GroupMembership.objects.filter(user=user).values(
                    "group_id", "group__name", "role", "joined_at",
                )
            ),
            "roadmap_shares": list(
                GroupRoadmapShare.objects.filter(shared_by=user).values(
                    "group_id", "group__name", "roadmap_id", "roadmap__title",
                    "created_at",
                )
            ),
            "threads": list(
                DiscussionThread.objects.filter(author=user).values(
                    "id", "group_id", "title", "body", "is_hidden",
                    "created_at", "updated_at",
                )
            ),
            "posts": list(
                DiscussionPost.objects.filter(author=user).values(
                    "id", "thread_id", "body", "is_deleted", "is_hidden",
                    "created_at", "updated_at",
                )
            ),
            "day_comments": list(
                DayComment.objects.filter(author=user).values(
                    "id", "day_id", "group_id", "body", "is_deleted",
                    "is_hidden", "created_at", "updated_at",
                )
            ),
            "reports": list(
                CommunityReport.objects.filter(reporter=user).values(
                    "id", "group_id", "target_type", "target_id", "reason",
                    "details", "status", "created_at",
                )
            ),
            "blocks": list(
                UserBlock.objects.filter(blocker=user).values(
                    "blocked_id", "blocked__username", "created_at",
                )
            ),
        },
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
