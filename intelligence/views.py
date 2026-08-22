from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import IntelligenceOnboardingForm
from .models import (
    DiagnosticAttempt,
    LearnerIntelligenceProfile,
    SkillPack,
    SkillState,
)
from .services.diagnostics import (
    get_or_create_current_attempt,
    next_diagnostic_stage,
    submit_diagnostic,
)


@login_required
def home(request):
    profile = LearnerIntelligenceProfile.objects.filter(user=request.user).first()
    if profile is None:
        return redirect("intelligence:onboarding")
    if not profile.diagnostics_complete:
        return redirect("intelligence:diagnostic")
    return redirect("intelligence:baseline")


@login_required
def onboarding(request):
    profile = LearnerIntelligenceProfile.objects.filter(user=request.user).first()
    original_pack_id = profile.selected_pack_id if profile else None
    if request.method == "POST":
        form = IntelligenceOnboardingForm(request.POST, instance=profile)
        if form.is_valid():
            selected_pack = form.cleaned_data["selected_pack"]
            pack_changed = original_pack_id is not None and original_pack_id != selected_pack.id
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
    profile = LearnerIntelligenceProfile.objects.filter(user=request.user).first()
    if profile is None:
        return redirect("intelligence:onboarding")
    attempt, definition = get_or_create_current_attempt(request.user, profile)
    if attempt is None:
        return redirect("intelligence:baseline")
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

    profile = LearnerIntelligenceProfile.objects.get(user=request.user)
    messages.success(
        request,
        f"Diagnostic completed: {attempt.score}/{attempt.question_count}.",
    )
    if next_diagnostic_stage(profile):
        return redirect("intelligence:diagnostic")
    return redirect("intelligence:baseline")


@login_required
def baseline(request):
    profile = LearnerIntelligenceProfile.objects.filter(user=request.user).select_related(
        "selected_pack"
    ).first()
    if profile is None:
        return redirect("intelligence:onboarding")
    if not profile.diagnostics_complete:
        return redirect("intelligence:diagnostic")

    pack_skill_ids = profile.selected_pack.memberships.values_list(
        "skill_id",
        flat=True,
    )
    states = list(
        SkillState.objects.filter(
            user=request.user,
            skill_id__in=pack_skill_ids,
        )
        .select_related("skill")
        .order_by("skill__domain", "skill__name")
    )
    attempts = list(
        DiagnosticAttempt.objects.filter(
            user=request.user,
            status="completed",
        ).order_by("started_at")
    )
    return render(
        request,
        "intelligence/baseline.html",
        {
            "profile": profile,
            "states": states,
            "attempts": attempts,
        },
    )
