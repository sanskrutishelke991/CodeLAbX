"""Approval-based adaptive roadmap revisions over immutable legacy roadmap days."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from intelligence.models import (
    LearnerIntelligenceProfile,
    Mission,
    RoadmapNode,
    RoadmapRevision,
    SkillPrerequisite,
)
from intelligence.services.recommendations import (
    TARGET_CONFIDENCE,
    TARGET_MASTERY,
    analyze_learning_dna,
)
from learning.models import Roadmap

ROUTE_ALGORITHM_VERSION = "skill-route-v1"
PACK_TOPIC_MAP = {
    "programming_dsa": "DSA",
    "machine_learning": "ML",
    "django_fullstack": "FULLSTACK",
}
POSTPONE_DAY_CHOICES = {1, 3, 7, 14, 30}


@dataclass(frozen=True)
class RouteDiffItem:
    node: RoadmapNode
    old_order: int | None
    new_order: int
    change: str

    @property
    def changed(self):
        return self.change != "unchanged"


@dataclass(frozen=True)
class RevisionDiff:
    items: tuple[RouteDiffItem, ...]
    removed_skill_names: tuple[str, ...]

    @property
    def changed_items(self):
        return tuple(item for item in self.items if item.changed)

    @property
    def changed_count(self):
        return len(self.changed_items) + len(self.removed_skill_names)


def compatible_topic_for_profile(profile):
    return PACK_TOPIC_MAP.get(profile.selected_pack.code)


def _validate_context(user, roadmap, profile):
    if roadmap.user_id != user.id:
        raise ValidationError("The roadmap does not belong to this learner.")
    if not isinstance(profile, LearnerIntelligenceProfile):
        raise ValidationError("A learner intelligence profile is required.")
    if profile.user_id != user.id:
        raise ValidationError("The learner profile does not belong to this learner.")
    expected_topic = compatible_topic_for_profile(profile)
    if expected_topic is None or roadmap.topic != expected_topic:
        raise ValidationError(
            "Choose a roadmap that matches the selected Skill Pack."
        )
    if roadmap.status not in {"active", "paused"}:
        raise ValidationError("Only active or paused roadmaps can be adapted.")


def _next_revision_number(roadmap):
    highest = (
        RoadmapRevision.objects.filter(roadmap=roadmap).aggregate(
            value=Max("revision_number")
        )["value"]
        or 0
    )
    return highest + 1


def _snapshot_key(profile, analysis):
    if analysis.recommendation_key:
        return analysis.recommendation_key
    payload = {
        "pack": [profile.selected_pack.code, profile.selected_pack.version],
        "skills": [item.skill.code for item in analysis.skills],
        "calculated_at": analysis.calculated_at.isoformat(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _node_status(dna, candidate):
    if (
        dna.has_evidence
        and dna.mastery >= TARGET_MASTERY
        and dna.confidence >= TARGET_CONFIDENCE
    ):
        return "complete"
    if candidate and candidate.eligible:
        return "ready"
    return "locked"


def _node_rationale(status):
    if status == "complete":
        return (
            "The current evidence snapshot meets the route mastery and confidence "
            "thresholds."
        )
    if status == "ready":
        return "Recorded prerequisite thresholds currently allow this skill."
    return "This skill remains locked until its recorded prerequisites are ready."


def _expected_minutes(skill):
    return min(90, 20 + (skill.difficulty_band * 10))


def _create_initial_revision_locked(user, roadmap, profile):
    current = (
        RoadmapRevision.objects.select_for_update()
        .filter(roadmap=roadmap, status="active")
        .first()
    )
    if current:
        return current, False

    analysis = analyze_learning_dna(user, profile)
    candidates = {
        candidate.dna.skill.id: candidate
        for candidate in analysis.candidates
    }
    now = analysis.calculated_at
    revision = RoadmapRevision.objects.create(
        roadmap=roadmap,
        revision_number=_next_revision_number(roadmap),
        status="active",
        reason_code="initial_skill_route",
        summary=(
            "Initial reviewed Skill Pack route. Existing roadmap days remain "
            "unchanged and continue to work normally."
        ),
        input_state_version=_snapshot_key(profile, analysis),
        input_state_at=now,
        algorithm_version=ROUTE_ALGORITHM_VERSION,
        decided_at=now,
    )
    for order, dna in enumerate(analysis.skills, start=1):
        status = _node_status(dna, candidates.get(dna.skill.id))
        RoadmapNode.objects.create(
            revision=revision,
            skill=dna.skill,
            order=order,
            status=status,
            rationale=_node_rationale(status),
            expected_minutes=_expected_minutes(dna.skill),
        )
    return revision, True


@transaction.atomic
def initialize_adaptive_route(user, roadmap, profile):
    locked_roadmap = Roadmap.objects.select_for_update().get(
        id=roadmap.id,
        user=user,
    )
    _validate_context(user, locked_roadmap, profile)
    return _create_initial_revision_locked(user, locked_roadmap, profile)


def _reorder_for_mission(nodes, target_skill_id):
    target = next(
        (node for node in nodes if node.skill_id == target_skill_id),
        None,
    )
    if target is None:
        raise ValidationError(
            "The mission skill is not part of this adaptive route."
        )
    target_index = nodes.index(target)
    if target.is_user_locked or target.status == "complete":
        return list(nodes)

    index_by_skill = {node.skill_id: index for index, node in enumerate(nodes)}
    prerequisite_ids = list(
        SkillPrerequisite.objects.filter(
            dependent_id=target_skill_id,
        ).values_list("prerequisite_id", flat=True)
    )
    earliest_index = 0
    for prerequisite_id in prerequisite_ids:
        if prerequisite_id in index_by_skill:
            earliest_index = max(
                earliest_index,
                index_by_skill[prerequisite_id] + 1,
            )

    fixed_indexes = {
        index
        for index, node in enumerate(nodes)
        if node.is_user_locked or node.status == "complete"
    }
    available_indexes = [
        index
        for index in range(len(nodes))
        if index not in fixed_indexes
    ]
    desired_index = next(
        (index for index in available_indexes if index >= earliest_index),
        target_index,
    )
    if desired_index == target_index:
        return list(nodes)

    result = [None] * len(nodes)
    for index in fixed_indexes:
        result[index] = nodes[index]
    result[desired_index] = target
    remaining = [
        node
        for index, node in enumerate(nodes)
        if index not in fixed_indexes and node.id != target.id
    ]
    iterator = iter(remaining)
    for index, value in enumerate(result):
        if value is None:
            result[index] = next(iterator)
    return result


@transaction.atomic
def propose_route_revision(user, roadmap, mission, profile):
    locked_roadmap = Roadmap.objects.select_for_update().get(
        id=roadmap.id,
        user=user,
    )
    _validate_context(user, locked_roadmap, profile)
    locked_mission = Mission.objects.select_for_update().get(
        id=mission.id,
        user=user,
    )
    if locked_mission.status != "proposed":
        raise ValidationError("Only a current proposed mission can change a route.")
    if not profile.selected_pack.memberships.filter(
        skill=locked_mission.primary_skill
    ).exists():
        raise ValidationError("The mission does not belong to the selected Skill Pack.")
    analysis = analyze_learning_dna(user, profile)
    if (
        analysis.recommendation is None
        or locked_mission.recommendation_key != analysis.recommendation_key
        or locked_mission.primary_skill_id
        != analysis.recommendation.dna.skill.id
    ):
        raise ValidationError(
            "This mission is stale. Recalculate Learning DNA before proposing a route."
        )
    if RoadmapRevision.objects.filter(
        trigger_mission=locked_mission,
        status__in={"proposed", "active", "postponed"},
    ).exclude(roadmap=locked_roadmap).exists():
        raise ValidationError("This mission is already attached to another route.")

    existing_proposal = (
        RoadmapRevision.objects.select_for_update()
        .filter(roadmap=locked_roadmap, status="proposed")
        .first()
    )
    if existing_proposal:
        if existing_proposal.trigger_mission_id == locked_mission.id:
            return existing_proposal, False
        raise ValidationError("Review the current route proposal before creating another.")
    if RoadmapRevision.objects.select_for_update().filter(
        roadmap=locked_roadmap,
        status="postponed",
    ).exists():
        raise ValidationError("Review the postponed route decision before creating another.")

    active, _created = _create_initial_revision_locked(
        user,
        locked_roadmap,
        profile,
    )
    active_nodes = list(
        active.nodes.select_related("skill", "mission").order_by("order")
    )
    ordered_nodes = _reorder_for_mission(
        active_nodes,
        locked_mission.primary_skill_id,
    )
    now = timezone.now()
    revision = RoadmapRevision.objects.create(
        roadmap=locked_roadmap,
        revision_number=_next_revision_number(locked_roadmap),
        status="proposed",
        reason_code="mission_proposal",
        summary=(
            f'Prioritize "{locked_mission.primary_skill.name}" through the '
            "current evidence-backed mission."
        ),
        input_state_version=locked_mission.recommendation_key,
        input_state_at=now,
        algorithm_version=ROUTE_ALGORITHM_VERSION,
        based_on=active,
        trigger_mission=locked_mission,
    )
    reason_messages = locked_mission.rationale.get("reason_messages", [])
    reason_text = " ".join(
        item for item in reason_messages if isinstance(item, str)
    )[:900]
    for order, source in enumerate(ordered_nodes, start=1):
        is_target = source.skill_id == locked_mission.primary_skill_id
        status = source.status
        if status == "active":
            status = "ready"
        if is_target and status != "complete":
            status = "ready"
        RoadmapNode.objects.create(
            revision=revision,
            skill=source.skill,
            mission=locked_mission if is_target else source.mission,
            order=order,
            status=status,
            rationale=(
                f"Mission proposal: {reason_text}"
                if is_target and reason_text
                else source.rationale
            ),
            expected_minutes=(
                locked_mission.expected_minutes
                if is_target
                else source.expected_minutes
            ),
            is_user_locked=source.is_user_locked,
        )
    return revision, True


def build_revision_diff(active_revision, proposed_revision):
    if proposed_revision.based_on_id != active_revision.id:
        raise ValidationError("The proposal is not based on the active revision.")
    old_nodes = {
        node.skill_id: node
        for node in active_revision.nodes.select_related("skill", "mission").all()
    }
    new_nodes = list(
        proposed_revision.nodes.select_related("skill", "mission").all()
    )
    items = []
    for node in new_nodes:
        old = old_nodes.get(node.skill_id)
        if old is None:
            change = "added"
            old_order = None
        elif old.order != node.order and old.mission_id != node.mission_id:
            change = "mission_and_move"
            old_order = old.order
        elif old.order > node.order:
            change = "moved_earlier"
            old_order = old.order
        elif old.order < node.order:
            change = "moved_later"
            old_order = old.order
        elif old.mission_id != node.mission_id:
            change = "mission_added"
            old_order = old.order
        else:
            change = "unchanged"
            old_order = old.order
        items.append(
            RouteDiffItem(
                node=node,
                old_order=old_order,
                new_order=node.order,
                change=change,
            )
        )
    new_skill_ids = {node.skill_id for node in new_nodes}
    removed = tuple(
        node.skill.name
        for node in old_nodes.values()
        if node.skill_id not in new_skill_ids
    )
    return RevisionDiff(tuple(items), removed)


def _owned_revision_for_update(user, roadmap, revision):
    locked_roadmap = Roadmap.objects.select_for_update().get(
        id=roadmap.id,
        user=user,
    )
    locked_revision = RoadmapRevision.objects.select_for_update().get(
        id=revision.id,
        roadmap=locked_roadmap,
    )
    return locked_roadmap, locked_revision


@transaction.atomic
def accept_revision(user, roadmap, revision):
    locked_roadmap, locked_revision = _owned_revision_for_update(
        user,
        roadmap,
        revision,
    )
    if locked_revision.status != "proposed":
        raise ValidationError("Only a proposed revision can be accepted.")
    active = (
        RoadmapRevision.objects.select_for_update()
        .filter(roadmap=locked_roadmap, status="active")
        .first()
    )
    if active is None or locked_revision.based_on_id != active.id:
        raise ValidationError("This proposal is stale and cannot be accepted.")
    now = timezone.now()
    active.status = "superseded"
    active.decided_at = now
    active.save(update_fields=["status", "decided_at"])
    locked_revision.status = "active"
    locked_revision.decided_at = now
    locked_revision.postponed_until = None
    locked_revision.save(
        update_fields=["status", "decided_at", "postponed_until"]
    )
    locked_revision.nodes.filter(status="active").update(status="ready")
    if locked_revision.trigger_mission_id:
        locked_revision.nodes.filter(
            mission_id=locked_revision.trigger_mission_id,
        ).exclude(status="complete").update(status="active")
        mission = Mission.objects.select_for_update().get(
            id=locked_revision.trigger_mission_id,
            user=user,
        )
        if mission.status == "proposed":
            mission.status = "accepted"
            mission.decided_at = now
            mission.postponed_until = None
            mission.save(
                update_fields=["status", "decided_at", "postponed_until"]
            )
    return locked_revision


@transaction.atomic
def reject_revision(user, roadmap, revision):
    _locked_roadmap, locked_revision = _owned_revision_for_update(
        user,
        roadmap,
        revision,
    )
    if locked_revision.status != "proposed":
        raise ValidationError("Only a proposed revision can be rejected.")
    now = timezone.now()
    locked_revision.status = "rejected"
    locked_revision.decided_at = now
    locked_revision.save(update_fields=["status", "decided_at"])
    if locked_revision.trigger_mission_id:
        mission = Mission.objects.select_for_update().get(
            id=locked_revision.trigger_mission_id,
            user=user,
        )
        if mission.status == "proposed":
            mission.status = "skipped"
            mission.decided_at = now
            mission.postponed_until = None
            mission.save(
                update_fields=["status", "decided_at", "postponed_until"]
            )
    return locked_revision


@transaction.atomic
def postpone_revision(user, roadmap, revision, *, days):
    if isinstance(days, bool) or days not in POSTPONE_DAY_CHOICES:
        raise ValidationError("Choose a supported postponement period.")
    _locked_roadmap, locked_revision = _owned_revision_for_update(
        user,
        roadmap,
        revision,
    )
    if locked_revision.status != "proposed":
        raise ValidationError("Only a proposed revision can be postponed.")
    now = timezone.now()
    review_at = now + timedelta(days=days)
    locked_revision.status = "postponed"
    locked_revision.decided_at = now
    locked_revision.postponed_until = review_at
    locked_revision.save(
        update_fields=["status", "decided_at", "postponed_until"]
    )
    if locked_revision.trigger_mission_id:
        mission = Mission.objects.select_for_update().get(
            id=locked_revision.trigger_mission_id,
            user=user,
        )
        if mission.status == "proposed":
            mission.status = "postponed"
            mission.decided_at = now
            mission.postponed_until = review_at
            mission.save(
                update_fields=["status", "decided_at", "postponed_until"]
            )
    return locked_revision


@transaction.atomic
def resume_revision(user, roadmap, revision):
    locked_roadmap, locked_revision = _owned_revision_for_update(
        user,
        roadmap,
        revision,
    )
    if locked_revision.status != "postponed":
        raise ValidationError("Only a postponed revision can be reviewed again.")
    if RoadmapRevision.objects.filter(
        roadmap=locked_roadmap,
        status="proposed",
    ).exists():
        raise ValidationError("Review the current route proposal first.")
    locked_revision.status = "proposed"
    locked_revision.decided_at = None
    locked_revision.postponed_until = None
    locked_revision.save(
        update_fields=["status", "decided_at", "postponed_until"]
    )
    if locked_revision.trigger_mission_id:
        mission = Mission.objects.select_for_update().get(
            id=locked_revision.trigger_mission_id,
            user=user,
        )
        if mission.status == "postponed":
            mission.status = "proposed"
            mission.decided_at = None
            mission.postponed_until = None
            mission.save(
                update_fields=["status", "decided_at", "postponed_until"]
            )
    return locked_revision


@transaction.atomic
def restore_revision(user, roadmap, revision):
    locked_roadmap, source = _owned_revision_for_update(
        user,
        roadmap,
        revision,
    )
    if source.status != "superseded":
        raise ValidationError("Only a superseded active revision can be restored.")
    if RoadmapRevision.objects.filter(
        roadmap=locked_roadmap,
        status__in={"proposed", "postponed"},
    ).exists():
        raise ValidationError(
            "Resolve the current or postponed proposal before restoring history."
        )
    current = (
        RoadmapRevision.objects.select_for_update()
        .filter(roadmap=locked_roadmap, status="active")
        .first()
    )
    if current is None:
        raise ValidationError("There is no active revision to replace.")
    now = timezone.now()
    current.status = "superseded"
    current.decided_at = now
    current.save(update_fields=["status", "decided_at"])
    signature = hashlib.sha256(
        f"restore:{source.id}:{current.id}:{now.isoformat()}".encode("utf-8")
    ).hexdigest()
    restored = RoadmapRevision.objects.create(
        roadmap=locked_roadmap,
        revision_number=_next_revision_number(locked_roadmap),
        status="active",
        reason_code="restored_revision",
        summary=f"Restored the route from revision {source.revision_number}.",
        input_state_version=signature,
        input_state_at=now,
        algorithm_version=ROUTE_ALGORITHM_VERSION,
        based_on=source,
        decided_at=now,
    )
    for node in source.nodes.select_related("skill", "mission").order_by("order"):
        RoadmapNode.objects.create(
            revision=restored,
            skill=node.skill,
            mission=node.mission,
            order=node.order,
            status="ready" if node.status == "active" else node.status,
            rationale=(
                f"Restored from revision {source.revision_number}: "
                f"{node.rationale}"
            )[:1000],
            expected_minutes=node.expected_minutes,
            is_user_locked=node.is_user_locked,
        )
    return restored


@transaction.atomic
def toggle_node_lock(user, roadmap, node):
    locked_roadmap = Roadmap.objects.select_for_update().get(
        id=roadmap.id,
        user=user,
    )
    locked_node = (
        RoadmapNode.objects.select_for_update()
        .select_related("revision")
        .get(id=node.id, revision__roadmap=locked_roadmap)
    )
    if locked_node.revision.status != "active":
        raise ValidationError("Only active-route nodes can be pinned.")
    if RoadmapRevision.objects.filter(
        roadmap=locked_roadmap,
        status__in={"proposed", "postponed"},
    ).exists():
        raise ValidationError(
            "Resolve the current or postponed proposal before changing pins."
        )
    if locked_node.status == "complete":
        raise ValidationError("Completed route nodes do not need a position pin.")
    locked_node.is_user_locked = not locked_node.is_user_locked
    locked_node.save(update_fields=["is_user_locked", "updated_at"])
    return locked_node
