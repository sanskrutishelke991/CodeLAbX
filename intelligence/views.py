from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from learning.models import Roadmap

from .forms import (
    AdaptiveRouteProposalForm,
    EvidenceFilterForm,
    IntelligenceOnboardingForm,
    PostponeRevisionForm,
)
from .models import (
    DiagnosticAttempt,
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    RoadmapNode,
    RoadmapRevision,
    Skill,
    SkillPack,
)
from .services.adaptive_roadmaps import (
    accept_revision,
    build_revision_diff,
    compatible_topic_for_profile,
    initialize_adaptive_route,
    postpone_revision,
    propose_route_revision,
    reject_revision,
    restore_revision,
    resume_revision,
    toggle_node_lock,
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
    except ValidationError:
        logger.info(
            "Initial mission was not reproposed for the current evidence snapshot",
            extra={"user_id": user.id},
        )
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
@transaction.atomic
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
                decision_time = timezone.now()
                RoadmapRevision.objects.filter(
                    roadmap__user=request.user,
                    status__in={"proposed", "postponed"},
                ).update(
                    status="rejected",
                    decided_at=decision_time,
                    postponed_until=None,
                )
                Mission.objects.filter(
                    user=request.user,
                    status__in={"proposed", "postponed"},
                ).update(
                    status="expired",
                    decided_at=decision_time,
                    postponed_until=None,
                )
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
    matching_mission = (
        Mission.objects.filter(
            user=request.user,
            recommendation_key=analysis.recommendation_key or "",
        )
        .select_related("primary_skill")
        .first()
    )
    current_mission = (
        matching_mission
        if matching_mission and matching_mission.status == "proposed"
        else None
    )
    mission_is_current = current_mission is not None
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
            "matching_mission": matching_mission,
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
    except ValidationError as exc:
        messages.info(request, exc.messages[0])
        return redirect("intelligence:dna")
    if mission.status == "proposed":
        action = "created" if created else "confirmed"
        messages.success(
            request,
            f"Mission proposal {action}: {mission.title}.",
        )
    else:
        messages.info(
            request,
            f'This evidence snapshot already has a {mission.get_status_display().lower()} mission.',
        )
    return redirect("intelligence:dna")


@login_required
def adaptive_routes(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    expected_topic = compatible_topic_for_profile(profile)
    roadmaps = list(
        Roadmap.objects.filter(
            user=request.user,
            topic=expected_topic or "",
        )
        .annotate(
            completed_days_count=Count(
                "days",
                filter=Q(days__is_completed=True),
                distinct=True,
            ),
            active_revision_count=Count(
                "intelligence_revisions",
                filter=Q(intelligence_revisions__status="active"),
                distinct=True,
            ),
            proposed_revision_count=Count(
                "intelligence_revisions",
                filter=Q(intelligence_revisions__status="proposed"),
                distinct=True,
            ),
        )
        .order_by("-updated_at")
    )
    missions = list(
        Mission.objects.filter(
            user=request.user,
            status__in={"proposed", "postponed"},
        )
        .select_related("primary_skill")
        .order_by("-created_at")
    )
    form = AdaptiveRouteProposalForm(
        user=request.user,
        profile=profile,
    )
    return render(
        request,
        "intelligence/adaptive_routes.html",
        {
            "profile": profile,
            "roadmaps": roadmaps,
            "missions": missions,
            "form": form,
            "can_propose": (
                form.fields["mission"].queryset.exists()
                and form.fields["roadmap"].queryset.exists()
            ),
            "expected_topic": dict(Roadmap.TOPIC_CHOICES).get(expected_topic, ""),
        },
    )


@login_required
def adaptive_route_detail(request, roadmap_id):
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    node_queryset = RoadmapNode.objects.select_related(
        "skill",
        "mission",
    ).order_by("order")
    revisions = list(
        RoadmapRevision.objects.filter(roadmap=roadmap)
        .select_related(
            "based_on",
            "trigger_mission",
            "trigger_mission__primary_skill",
        )
        .prefetch_related(Prefetch("nodes", queryset=node_queryset))
        .order_by("-revision_number")
    )
    active_revision = next(
        (revision for revision in revisions if revision.status == "active"),
        None,
    )
    proposed_revision = next(
        (revision for revision in revisions if revision.status == "proposed"),
        None,
    )
    postponed_revisions = tuple(
        revision for revision in revisions if revision.status == "postponed"
    )
    revision_diff = None
    if active_revision and proposed_revision:
        revision_diff = build_revision_diff(active_revision, proposed_revision)
    display_revision = proposed_revision or active_revision
    display_nodes = tuple(display_revision.nodes.all()) if display_revision else ()
    available_mission = (
        Mission.objects.filter(
            user=request.user,
            status="proposed",
            primary_skill__pack_memberships__pack=profile.selected_pack,
        )
        .exclude(
            roadmap_revisions__status__in={
                "proposed",
                "active",
                "postponed",
            }
        )
        .select_related("primary_skill")
        .distinct()
        .order_by("-created_at")
        .first()
    )
    proposal_form = AdaptiveRouteProposalForm(
        user=request.user,
        profile=profile,
        initial={
            "roadmap": roadmap,
            "mission": available_mission,
        },
    )
    return render(
        request,
        "intelligence/adaptive_route_detail.html",
        {
            "profile": profile,
            "roadmap": roadmap,
            "revisions": revisions,
            "active_revision": active_revision,
            "proposed_revision": proposed_revision,
            "postponed_revisions": postponed_revisions,
            "revision_diff": revision_diff,
            "display_revision": display_revision,
            "display_nodes": display_nodes,
            "available_mission": available_mission,
            "proposal_form": proposal_form,
            "postpone_form": PostponeRevisionForm(),
            "profile_matches_roadmap": (
                roadmap.topic == compatible_topic_for_profile(profile)
            ),
            "legacy_day_count": roadmap.days.count(),
            "legacy_completed_count": roadmap.days.filter(
                is_completed=True
            ).count(),
        },
    )


@login_required
@require_POST
def initialize_route(request, roadmap_id):
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    try:
        _revision, created = initialize_adaptive_route(
            request.user,
            roadmap,
            profile,
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(
            request,
            "Adaptive skill route initialized. Legacy roadmap days were not changed."
            if created
            else "The adaptive skill route is already initialized.",
        )
    return redirect(
        "intelligence:adaptive_route_detail",
        roadmap_id=roadmap.id,
    )


@login_required
@require_POST
def create_route_proposal(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    form = AdaptiveRouteProposalForm(
        request.POST,
        user=request.user,
        profile=profile,
    )
    if not form.is_valid():
        messages.error(request, "Choose a current mission and matching roadmap.")
        return redirect("intelligence:adaptive_routes")
    roadmap = form.cleaned_data["roadmap"]
    mission = form.cleaned_data["mission"]
    try:
        revision, created = propose_route_revision(
            request.user,
            roadmap,
            mission,
            profile,
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect("intelligence:adaptive_routes")
    messages.success(
        request,
        "A route change is ready for your review. Nothing was applied automatically."
        if created
        else "That route proposal is already waiting for review.",
    )
    return redirect(
        "intelligence:adaptive_route_detail",
        roadmap_id=revision.roadmap_id,
    )


@login_required
@require_POST
def revision_action(request, roadmap_id, revision_id, action):
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )
    revision = get_object_or_404(
        RoadmapRevision,
        id=revision_id,
        roadmap=roadmap,
    )
    try:
        if action == "accept":
            accept_revision(request.user, roadmap, revision)
            messages.success(
                request,
                "Route revision accepted. Legacy roadmap days remain unchanged.",
            )
        elif action == "reject":
            reject_revision(request.user, roadmap, revision)
            messages.info(request, "Route revision rejected and recorded.")
        elif action == "postpone":
            form = PostponeRevisionForm(request.POST)
            if not form.is_valid():
                raise ValidationError("Choose a supported postponement period.")
            postpone_revision(
                request.user,
                roadmap,
                revision,
                days=form.cleaned_data["days"],
            )
            messages.info(request, "Route revision postponed.")
        elif action == "resume":
            resume_revision(request.user, roadmap, revision)
            messages.success(request, "The postponed revision is ready for review.")
        else:
            raise ValidationError("That revision action is not supported.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect(
        "intelligence:adaptive_route_detail",
        roadmap_id=roadmap.id,
    )


@login_required
@require_POST
def restore_route_revision(request, roadmap_id, revision_id):
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )
    revision = get_object_or_404(
        RoadmapRevision,
        id=revision_id,
        roadmap=roadmap,
    )
    try:
        restored = restore_revision(request.user, roadmap, revision)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(
            request,
            f"Revision {revision.revision_number} was restored as revision "
            f"{restored.revision_number}.",
        )
    return redirect(
        "intelligence:adaptive_route_detail",
        roadmap_id=roadmap.id,
    )


@login_required
@require_POST
def toggle_route_node_lock(request, roadmap_id, node_id):
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )
    node = get_object_or_404(
        RoadmapNode,
        id=node_id,
        revision__roadmap=roadmap,
    )
    try:
        updated = toggle_node_lock(request.user, roadmap, node)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(
            request,
            "Node position pinned."
            if updated.is_user_locked
            else "Node position unpinned.",
        )
    return redirect(
        "intelligence:adaptive_route_detail",
        roadmap_id=roadmap.id,
    )
