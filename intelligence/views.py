from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import EvidenceFilterForm, IntelligenceOnboardingForm
from .models import (
    DiagnosticAttempt,
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    Skill,
    SkillPack,
)
from .services.diagnostics import (
    get_or_create_current_attempt,
    next_diagnostic_stage,
    submit_diagnostic,
)
from .services.recommendations import (
    analyze_learning_dna,
    propose_next_mission,
)

logger = logging.getLogger(__name__)


def _profile_for(user):
    return (
        LearnerIntelligenceProfile.objects.filter(user=user)
        .select_related("selected_pack")
        .first()
    )


def _completed_profile_or_redirect(user):
    profile = _profile_for(user)
    if profile is None:
        return None, redirect("intelligence:onboarding")
    if not profile.diagnostics_complete:
        return None, redirect("intelligence:diagnostic")
    return profile, None


def _try_initial_mission(user, profile):
    try:
        propose_next_mission(user, profile)
    except Exception:
        logger.exception("Initial Learning Intelligence mission proposal failed")


@login_required
def home(request):
    profile = _profile_for(request.user)
    if profile is None:
        return redirect("intelligence:onboarding")
    if not profile.diagnostics_complete:
        return redirect("intelligence:diagnostic")
    return redirect("intelligence:dna")


@login_required
def onboarding(request):
    profile = LearnerIntelligenceProfile.objects.filter(user=request.user).first()
    original_pack_id = profile.selected_pack_id if profile else None
    if request.method == "POST":
        form = IntelligenceOnboardingForm(request.POST, instance=profile)
        if form.is_valid():
            selected_pack = form.cleaned_data["selected_pack"]
            pack_changed = (
                original_pack_id is not None
                and original_pack_id != selected_pack.id
            )
            profile = form.save(commit=False)
            profile.user = request.user
            if pack_changed:
                profile.routing_diagnostic_completed_at = None
                profile.goal_diagnostic_completed_at = None
                DiagnosticAttempt.objects.filter(
                    user=request.user,
                    status="started",
                ).delete()
            profile.full_clean()
            profile.save()
            if pack_changed:
                Mission.objects.filter(
                    user=request.user,
                    status="proposed",
                ).update(status="expired", decided_at=timezone.now())
            messages.success(
                request,
                "Learning Intelligence preferences saved. Start the diagnostic when ready.",
            )
            return redirect("intelligence:diagnostic")
    else:
        form = IntelligenceOnboardingForm(instance=profile)

    if not SkillPack.objects.filter(is_active=True).exclude(code="shared_core").exists():
        messages.warning(
            request,
            "Skill Packs are not seeded yet. Run the Skill Pack seed command.",
        )
    return render(
        request,
        "intelligence/onboarding.html",
        {"form": form, "profile": profile},
    )


@login_required
def diagnostic(request):
    profile = _profile_for(request.user)
    if profile is None:
        return redirect("intelligence:onboarding")
    attempt, definition = get_or_create_current_attempt(request.user, profile)
    if attempt is None:
        return redirect("intelligence:dna")
    return render(
        request,
        "intelligence/diagnostic.html",
        {
            "profile": profile,
            "attempt": attempt,
            "diagnostic": definition,
            "questions": definition.public_questions,
        },
    )


@login_required
@require_POST
def diagnostic_submit(request):
    try:
        attempt_id = int(request.POST.get("attempt_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "The diagnostic attempt is invalid.")
        return redirect("intelligence:diagnostic")
    answers = {
        key.removeprefix("answer_"): value
        for key, value in request.POST.items()
        if key.startswith("answer_")
    }
    try:
        attempt = submit_diagnostic(request.user, attempt_id, answers)
    except (
        ValidationError,
        DiagnosticAttempt.DoesNotExist,
        LearnerIntelligenceProfile.DoesNotExist,
    ):
        messages.error(
            request,
            "The diagnostic could not be submitted. Review every answer and try again.",
        )
        return redirect("intelligence:diagnostic")

    profile = _profile_for(request.user)
    messages.success(
        request,
        f"Diagnostic completed: {attempt.score}/{attempt.question_count}.",
    )
    if next_diagnostic_stage(profile):
        return redirect("intelligence:diagnostic")
    _try_initial_mission(request.user, profile)
    return redirect("intelligence:dna")


@login_required
def dna(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    analysis = analyze_learning_dna(request.user, profile)
    grouped_skills = {}
    for item in analysis.skills:
        grouped_skills.setdefault(item.skill.domain, []).append(item)
    domain_groups = [
        (domain, tuple(items))
        for domain, items in grouped_skills.items()
    ]
    attempts = list(
        DiagnosticAttempt.objects.filter(
            user=request.user,
            status="completed",
        ).order_by("started_at")
    )
    ledger_event_count = LearningEvent.objects.filter(user=request.user).count()
    current_mission = (
        Mission.objects.filter(user=request.user, status="proposed")
        .select_related("primary_skill")
        .order_by("-created_at")
        .first()
    )
    mission_is_current = bool(
        current_mission
        and current_mission.recommendation_key == analysis.recommendation_key
    )
    return render(
        request,
        "intelligence/baseline.html",
        {
            "profile": profile,
            "analysis": analysis,
            "domain_groups": domain_groups,
            "attempts": attempts,
            "ledger_event_count": ledger_event_count,
            "current_mission": current_mission,
            "mission_is_current": mission_is_current,
        },
    )


@login_required
def evidence_explorer(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    available_skills = list(
        Skill.objects.filter(
            Q(pack_memberships__pack=profile.selected_pack)
            | Q(learning_events__user=request.user)
        )
        .distinct()
        .order_by("domain", "name")
    )
    form = EvidenceFilterForm(
        request.GET or None,
        skill_choices=[
            (skill.code, f"{skill.name} ({skill.domain})")
            for skill in available_skills
        ],
    )
    events = LearningEvent.objects.filter(user=request.user).select_related("skill")
    if form.is_valid():
        skill_code = form.cleaned_data["skill"]
        event_type = form.cleaned_data["event_type"]
        if skill_code:
            events = events.filter(skill__code=skill_code)
        if event_type:
            events = events.filter(event_type=event_type)
    else:
        events = events.none()
        skill_code = ""
        event_type = ""

    page_obj = Paginator(events.order_by("-occurred_at", "-id"), 20).get_page(
        request.GET.get("page")
    )
    for event in page_obj.object_list:
        if event.outcome is None:
            event.display_outcome = "Observed, not scoreable"
            event.outcome_percent = None
        else:
            event.outcome_percent = round(float(event.outcome) * 100)
            event.display_outcome = f"{event.outcome_percent}% outcome"
        event.difficulty_percent = round(float(event.difficulty) * 100)
        misconceptions = event.metadata.get("misconception_codes", [])
        event.display_misconceptions = (
            tuple(item for item in misconceptions if isinstance(item, str))
            if isinstance(misconceptions, list)
            else ()
        )

    return render(
        request,
        "intelligence/evidence.html",
        {
            "profile": profile,
            "form": form,
            "page_obj": page_obj,
            "selected_skill": skill_code,
            "selected_event_type": event_type,
        },
    )


@login_required
@require_POST
def recalculate_recommendation(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    try:
        mission, created, _analysis = propose_next_mission(
            request.user,
            profile,
        )
    except ValidationError:
        messages.error(
            request,
            "No eligible mission could be proposed from the current Skill Pack.",
        )
        return redirect("intelligence:dna")
    action = "created" if created else "confirmed"
    messages.success(
        request,
        f"Mission proposal {action}: {mission.title}.",
    )
    return redirect("intelligence:dna")
