"""Privacy-minimized, explicit, revocable public learning snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from intelligence.models import (
    LearnerIntelligenceProfile,
    PublicShare,
    RoadmapRevision,
)
from intelligence.services.passport import build_skill_passport
from learning.models import Roadmap

PUBLIC_SNAPSHOT_VERSION = 1
MAX_PUBLIC_ITEMS = 100


@dataclass(frozen=True)
class PublicSnapshotResult:
    share: PublicShare
    created: bool


def _snapshot_hash(snapshot):
    encoded = json.dumps(
        snapshot,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _passport_snapshot(user, *, include_evidence_counts):
    profile = (
        LearnerIntelligenceProfile.objects.filter(user=user)
        .select_related("selected_pack")
        .first()
    )
    if profile is None or not profile.diagnostics_complete:
        raise ValidationError(
            "Complete Learning Intelligence diagnostics before sharing a Passport snapshot."
        )
    passport = build_skill_passport(user, profile)
    skills = []
    for item in passport.skills:
        if not item.dna.has_evidence:
            continue
        skill = {
            "code": item.dna.skill.code,
            "name": item.dna.skill.name,
            "domain": item.dna.skill.domain,
            "mastery_percent": item.dna.mastery_percent,
            "confidence_percent": item.dna.confidence_percent,
            "freshness_percent": item.dna.freshness_percent,
            "evidence_level": item.evidence_level,
        }
        if include_evidence_counts:
            skill["evidence"] = {
                "scoreable": item.scoreable_event_count,
                "deterministic": item.deterministic_event_count,
                "supporting": item.supporting_scoreable_count,
                "observed_non_scoreable": item.observed_only_count,
            }
        skills.append(skill)
    return {
        "kind": "passport",
        "version": PUBLIC_SNAPSHOT_VERSION,
        "generated_at": timezone.now().isoformat(),
        "pack": {
            "code": profile.selected_pack.code,
            "name": profile.selected_pack.name,
            "version": profile.selected_pack.version,
        },
        "trust_label": "Evidence observed — not independently verified",
        "observed_skill_count": passport.observed_skill_count,
        "total_pack_skills": len(passport.skills),
        "skills": skills[:MAX_PUBLIC_ITEMS],
    }


def _roadmap_snapshot(user, roadmap, *, include_completed_items):
    if not isinstance(roadmap, Roadmap) or roadmap.user_id != user.id:
        raise ValidationError("The roadmap does not belong to this user.")
    completed_days = roadmap.days.filter(is_completed=True).count()
    snapshot = {
        "kind": "roadmap",
        "version": PUBLIC_SNAPSHOT_VERSION,
        "generated_at": timezone.now().isoformat(),
        "roadmap": {
            "title": roadmap.title,
            "topic": roadmap.get_topic_display(),
            "level": roadmap.get_level_display(),
            "status": roadmap.get_status_display(),
            "total_days": roadmap.total_days,
            "completed_days": completed_days,
            "progress_percent": (
                round(completed_days / roadmap.total_days * 100, 1)
                if roadmap.total_days
                else 0
            ),
        },
        "trust_label": (
            "Learner-controlled roadmap progress — not a certificate or skill verification"
        ),
    }
    if include_completed_items:
        snapshot["days"] = list(
            roadmap.days.order_by("day_number").values(
                "day_number",
                "title",
                "is_completed",
            )[:MAX_PUBLIC_ITEMS]
        )
    active_revision = (
        RoadmapRevision.objects.filter(roadmap=roadmap, status="active")
        .prefetch_related("nodes__skill")
        .order_by("-revision_number")
        .first()
    )
    if active_revision:
        snapshot["adaptive_route"] = {
            "revision": active_revision.revision_number,
            "nodes": [
                {
                    "order": node.order,
                    "skill": node.skill.name,
                    "domain": node.skill.domain,
                    "status": node.get_status_display(),
                    "expected_minutes": node.expected_minutes,
                    "learner_pinned": node.is_user_locked,
                }
                for node in active_revision.nodes.all()[:MAX_PUBLIC_ITEMS]
            ],
        }
    return snapshot


def build_public_snapshot(
    user,
    *,
    share_type,
    roadmap=None,
    include_evidence_counts=True,
    include_completed_items=True,
):
    if share_type == "passport":
        return _passport_snapshot(
            user,
            include_evidence_counts=include_evidence_counts,
        )
    if share_type == "roadmap":
        return _roadmap_snapshot(
            user,
            roadmap,
            include_completed_items=include_completed_items,
        )
    raise ValidationError("That public share type is not supported.")


@transaction.atomic
def create_or_refresh_public_share(
    user,
    *,
    share_type,
    display_name,
    roadmap=None,
    include_evidence_counts=True,
    include_completed_items=True,
):
    user.__class__.objects.select_for_update().get(pk=user.pk)
    snapshot = build_public_snapshot(
        user,
        share_type=share_type,
        roadmap=roadmap,
        include_evidence_counts=include_evidence_counts,
        include_completed_items=include_completed_items,
    )
    query = PublicShare.objects.select_for_update().filter(
        user=user,
        share_type=share_type,
        is_active=True,
    )
    if share_type == "roadmap":
        query = query.filter(roadmap=roadmap)
    share = query.first()
    created = share is None
    if share is None:
        share = PublicShare(
            user=user,
            share_type=share_type,
            roadmap=roadmap,
        )
    share.display_name = display_name
    share.include_evidence_counts = include_evidence_counts
    share.include_completed_items = include_completed_items
    share.snapshot = snapshot
    share.snapshot_hash = _snapshot_hash(snapshot)
    share.snapshot_version = PUBLIC_SNAPSHOT_VERSION
    share.refreshed_at = timezone.now()
    share.is_active = True
    share.revoked_at = None
    share.save()
    return PublicSnapshotResult(share=share, created=created)


@transaction.atomic
def refresh_public_share(user, share):
    share = PublicShare.objects.select_for_update().get(
        id=share.id,
        user=user,
        is_active=True,
    )
    snapshot = build_public_snapshot(
        user,
        share_type=share.share_type,
        roadmap=share.roadmap,
        include_evidence_counts=share.include_evidence_counts,
        include_completed_items=share.include_completed_items,
    )
    share.snapshot = snapshot
    share.snapshot_hash = _snapshot_hash(snapshot)
    share.refreshed_at = timezone.now()
    share.save()
    return share


@transaction.atomic
def revoke_public_share(user, share):
    share = PublicShare.objects.select_for_update().get(
        id=share.id,
        user=user,
        is_active=True,
    )
    share.is_active = False
    share.revoked_at = timezone.now()
    share.save()
    return share
