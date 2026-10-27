from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from learning.models import Roadmap

from .forms import (
    AdaptiveRouteProposalForm,
    EvidenceFilterForm,
    IntelligenceOnboardingForm,
    PostponeRevisionForm,
    PublicShareForm,
    TutorFeedbackForm,
    TutorMemoryForm,
    TutorPreferenceForm,
)
from .models import (
    DiagnosticAttempt,
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    PublicShare,
    RoadmapNode,
    RoadmapRevision,
    Skill,
    SkillPack,
    TutorFeedback,
    TutorMemory,
    TutorPreference,
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
from .services.passport import build_skill_passport
from .services.public_sharing import (
    create_or_refresh_public_share,
    refresh_public_share,
    revoke_public_share,
)
from .services.recommendations import (
    analyze_learning_dna,
    propose_next_mission,
)
from .services.retention import (
    BLOCKING_MISSION_STATUSES,
    analyze_retention,
    create_retention_mission,
)
from .services.tutor_context import (
    build_tutor_context,
    record_tutor_feedback,
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


@login_required
def tutor_home(request):
    if TutorPreference.objects.filter(user=request.user).exists():
        return redirect("intelligence:tutor_memory")
    return redirect("intelligence:tutor_preferences")


@login_required
def tutor_preferences(request):
    preference = TutorPreference.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = TutorPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            preference = form.save(commit=False)
            preference.user = request.user
            if preference.onboarding_completed_at is None:
                preference.onboarding_completed_at = timezone.now()
            preference.save()
            messages.success(
                request,
                "Tutor preferences saved. You remain in control of every memory.",
            )
            return redirect("intelligence:tutor_memory")
    else:
        form = TutorPreferenceForm(instance=preference)
    return render(
        request,
        "intelligence/tutor_preferences.html",
        {"form": form, "preference": preference},
    )


def _render_tutor_memory(request, *, memory_form=None, status=200):
    preference = TutorPreference.objects.filter(user=request.user).first()
    if preference is None:
        return redirect("intelligence:tutor_preferences")
    if memory_form is None:
        initial = None
        requested_session = request.GET.get("session", "").strip()
        if len(requested_session) <= 20 and requested_session.isdigit():
            session = request.user.chat_sessions.filter(
                id=int(requested_session)
            ).first()
            if session:
                initial = {
                    "category": "session_summary",
                    "chat_session": session,
                    "reason": "Learner-approved compact session summary.",
                }
        memory_form = TutorMemoryForm(user=request.user, initial=initial)
    memories = (
        TutorMemory.objects.filter(user=request.user)
        .select_related("chat_session")
        .order_by("-is_active", "-updated_at")
    )
    page_obj = Paginator(memories, 20).get_page(request.GET.get("page"))
    feedback_counts = list(
        TutorFeedback.objects.filter(user=request.user)
        .values("feedback_type")
        .annotate(total=Count("id"))
        .order_by("feedback_type")
    )
    feedback_labels = dict(TutorFeedback.FEEDBACK_CHOICES)
    for item in feedback_counts:
        item["label"] = feedback_labels[item["feedback_type"]]
    context = build_tutor_context(request.user)
    return render(
        request,
        "intelligence/tutor_memory.html",
        {
            "preference": preference,
            "memory_form": memory_form,
            "memories": page_obj,
            "page_obj": page_obj,
            "feedback_counts": feedback_counts,
            "context": context,
            "active_memory_count": TutorMemory.objects.filter(
                user=request.user,
                is_active=True,
            ).count(),
        },
        status=status,
    )


@login_required
def tutor_memory(request):
    return _render_tutor_memory(request)


@login_required
@require_POST
def tutor_memory_add(request):
    if not TutorPreference.objects.filter(user=request.user).exists():
        return redirect("intelligence:tutor_preferences")
    form = TutorMemoryForm(request.POST, user=request.user)
    if form.is_valid():
        memory = form.save()
        messages.success(
            request,
            f"Tutor memory saved: {memory.get_category_display()}.",
        )
        return redirect("intelligence:tutor_memory")
    return _render_tutor_memory(request, memory_form=form, status=400)


@login_required
def tutor_memory_update(request, memory_id):
    memory = get_object_or_404(
        TutorMemory,
        id=memory_id,
        user=request.user,
    )
    if request.method == "POST":
        form = TutorMemoryForm(
            request.POST,
            instance=memory,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Tutor memory updated and confirmed.")
            return redirect("intelligence:tutor_memory")
    else:
        form = TutorMemoryForm(instance=memory, user=request.user)
    return render(
        request,
        "intelligence/tutor_memory_form.html",
        {"form": form, "memory": memory},
    )


@login_required
@require_POST
def tutor_memory_delete(request, memory_id):
    memory = get_object_or_404(
        TutorMemory,
        id=memory_id,
        user=request.user,
    )
    if (
        memory.source_type == "observed_feedback"
        and memory.source_key.startswith("feedback-pattern:")
    ):
        feedback_type = memory.source_key.removeprefix("feedback-pattern:")
        TutorFeedback.objects.filter(
            user=request.user,
            feedback_type=feedback_type,
        ).delete()
    memory.delete()
    messages.success(request, "Tutor memory permanently deleted.")
    return redirect("intelligence:tutor_memory")


@login_required
@require_POST
@transaction.atomic
def tutor_memory_forget_all(request):
    if request.POST.get("confirmation") != "forget":
        messages.error(request, "Forget-all was not confirmed.")
        return redirect("intelligence:tutor_memory")
    memory_count, _ = TutorMemory.objects.filter(user=request.user).delete()
    TutorFeedback.objects.filter(user=request.user).delete()
    messages.success(
        request,
        f"Forgot {memory_count} tutor memory item(s) and all tutor feedback signals.",
    )
    return redirect("intelligence:tutor_memory")


@login_required
@require_POST
def tutor_feedback(request):
    form = TutorFeedbackForm(request.POST, user=request.user)
    if not form.is_valid():
        return JsonResponse(
            {
                "success": False,
                "error": "Choose feedback for one of your assistant responses.",
            },
            status=400,
        )
    result = record_tutor_feedback(
        request.user,
        form.cleaned_data["message"],
        form.cleaned_data["feedback_type"],
    )
    return JsonResponse(
        {
            "success": True,
            "feedback": result.feedback.feedback_type,
            "adaptation_created": result.adaptation_created,
            "message": (
                "Feedback saved. A visible memory suggestion was added."
                if result.adaptation_created
                else "Feedback saved."
            ),
        }
    )


@login_required
def skill_passport(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    passport = build_skill_passport(request.user, profile)
    grouped = {}
    unobserved = []
    for item in passport.skills:
        if item.dna.has_evidence:
            grouped.setdefault(item.dna.skill.domain, []).append(item)
        else:
            unobserved.append(item)
    return render(
        request,
        "intelligence/passport.html",
        {
            "profile": profile,
            "passport": passport,
            "domain_groups": [
                (domain, tuple(items)) for domain, items in grouped.items()
            ],
            "unobserved": tuple(unobserved),
        },
    )


@login_required
def retention_center(request):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    analysis = analyze_retention(request.user, profile)
    skill_ids = [item.dna.skill.id for item in analysis.candidates]
    mission_by_key = {}
    for mission in (
        Mission.objects.filter(
            user=request.user,
            mission_type="retention",
            primary_skill_id__in=skill_ids,
        )
        .select_related("primary_skill")
        .order_by("-created_at")
    ):
        mission_by_key.setdefault(mission.recommendation_key, mission)
    rows = tuple(
        {
            "candidate": candidate,
            "mission": mission_by_key.get(candidate.recommendation_key),
        }
        for candidate in analysis.candidates
    )
    blocking_mission = (
        Mission.objects.filter(
            user=request.user,
            status__in=BLOCKING_MISSION_STATUSES,
        )
        .select_related("primary_skill")
        .order_by("-created_at")
        .first()
    )
    return render(
        request,
        "intelligence/retention.html",
        {
            "profile": profile,
            "analysis": analysis,
            "rows": rows,
            "blocking_mission": blocking_mission,
        },
    )


@login_required
@require_POST
def create_refresh_mission(request, skill_id):
    profile, response = _completed_profile_or_redirect(request.user)
    if response:
        return response
    skill = get_object_or_404(
        Skill,
        id=skill_id,
        is_active=True,
        pack_memberships__pack=profile.selected_pack,
    )
    try:
        mission, created, _candidate = create_retention_mission(
            request.user,
            profile,
            skill,
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        if created:
            messages.success(
                request,
                f"Refresh mission proposed: {mission.title}.",
            )
        else:
            messages.info(
                request,
                f"That refresh snapshot already has a {mission.get_status_display().lower()} mission.",
            )
    return redirect("intelligence:retention")


@login_required
def sharing_dashboard(request):
    profile = _profile_for(request.user)
    shares = list(
        PublicShare.objects.filter(user=request.user)
        .select_related("roadmap")
        .order_by("-is_active", "-created_at")[:30]
    )
    for share in shares:
        share.public_url = request.build_absolute_uri(
            reverse("intelligence:public_share", args=[share.public_id])
        )
    roadmaps = list(
        Roadmap.objects.filter(user=request.user)
        .annotate(
            completed_days_count=Count(
                "days",
                filter=Q(days__is_completed=True),
            )
        )
        .order_by("-updated_at")[:30]
    )
    roadmap_rows = [
        {
            "roadmap": roadmap,
            "form": PublicShareForm(
                share_type="roadmap",
                auto_id=f"id_roadmap_{roadmap.id}_%s",
            ),
        }
        for roadmap in roadmaps
    ]
    return render(
        request,
        "intelligence/sharing.html",
        {
            "profile": profile,
            "passport_ready": bool(profile and profile.diagnostics_complete),
            "shares": shares,
            "roadmap_rows": roadmap_rows,
            "passport_form": PublicShareForm(share_type="passport"),
        },
    )


@login_required
@require_POST
def create_passport_share(request):
    form = PublicShareForm(request.POST, share_type="passport")
    if not form.is_valid():
        messages.error(
            request,
            "Confirm the public link and choose a valid display name.",
        )
        return redirect("intelligence:sharing")
    try:
        result = create_or_refresh_public_share(
            request.user,
            share_type="passport",
            display_name=form.cleaned_data["display_name"],
            include_evidence_counts=form.cleaned_data.get(
                "include_evidence_counts",
                False,
            ),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(
            request,
            "Public Passport link created. It is no-index and remains active until you revoke it."
            if result.created
            else "Existing public Passport snapshot refreshed.",
        )
    return redirect("intelligence:sharing")


@login_required
@require_POST
def create_roadmap_share(request, roadmap_id):
    roadmap = get_object_or_404(
        Roadmap,
        id=roadmap_id,
        user=request.user,
    )
    form = PublicShareForm(request.POST, share_type="roadmap")
    if not form.is_valid():
        messages.error(
            request,
            "Confirm the public link and choose a valid display name.",
        )
        return redirect("intelligence:sharing")
    try:
        result = create_or_refresh_public_share(
            request.user,
            share_type="roadmap",
            roadmap=roadmap,
            display_name=form.cleaned_data["display_name"],
            include_completed_items=form.cleaned_data.get(
                "include_completed_items",
                False,
            ),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(
            request,
            "Public roadmap link created. It is no-index and remains active until you revoke it."
            if result.created
            else "Existing public roadmap snapshot refreshed.",
        )
    return redirect("intelligence:sharing")


@login_required
@require_POST
def refresh_share(request, share_id):
    share = get_object_or_404(
        PublicShare,
        id=share_id,
        user=request.user,
        is_active=True,
    )
    try:
        refresh_public_share(request.user, share)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Public snapshot refreshed from current records.")
    return redirect("intelligence:sharing")


@login_required
@require_POST
def revoke_share(request, share_id):
    share = get_object_or_404(
        PublicShare,
        id=share_id,
        user=request.user,
        is_active=True,
    )
    revoke_public_share(request.user, share)
    messages.success(request, "Public share revoked. The old link now returns Gone.")
    return redirect("intelligence:sharing")


def public_share(request, public_id):
    share = get_object_or_404(
        PublicShare.objects.select_related("roadmap"),
        public_id=public_id,
    )
    if not share.is_active:
        response = render(
            request,
            "intelligence/public_share_revoked.html",
            status=410,
        )
    else:
        response = render(
            request,
            "intelligence/public_share.html",
            {"share": share, "snapshot": share.snapshot},
        )
    response["Cache-Control"] = "no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
