from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from learning.forms import RoadmapCreateForm
from learning.models import Day, Roadmap
from learning.services import RoadmapGenerator

from .models import (
    LearnerIntelligenceProfile,
    Mission,
    RoadmapNode,
    RoadmapRevision,
    Skill,
    SkillPack,
    SkillState,
)
from .services.adaptive_roadmaps import (
    ROUTE_ALGORITHM_VERSION,
    accept_revision,
    build_revision_diff,
    initialize_adaptive_route,
    postpone_revision,
    propose_route_revision,
    reject_revision,
    restore_revision,
    resume_revision,
    toggle_node_lock,
)
from .services.recommendations import propose_next_mission
from .services.skill_packs import seed_skill_packs


def create_complete_profile(user, pack):
    now = timezone.now()
    return LearnerIntelligenceProfile.objects.create(
        user=user,
        primary_goal="placement",
        selected_pack=pack,
        routing_diagnostic_completed_at=now,
        goal_diagnostic_completed_at=now,
    )


def create_debugging_evidence(user):
    now = timezone.now()
    values = {
        "computing.computational_thinking": ("0.8500", "0.8000"),
        "programming.problem_decomposition": ("0.8500", "0.8000"),
        "programming.debugging": ("0.2000", "0.8000"),
    }
    for code, (mastery, confidence) in values.items():
        skill = Skill.objects.get(code=code)
        SkillState.objects.create(
            user=user,
            skill=skill,
            mastery=Decimal(mastery),
            confidence=Decimal(confidence),
            freshness=Decimal("1.0000"),
            evidence_count=6,
            total_evidence_weight=Decimal("6.000"),
            last_evidence_at=now,
        )


def create_roadmap(user, *, topic="DSA", title="Adaptive DSA roadmap"):
    roadmap = Roadmap.objects.create(
        user=user,
        topic=topic,
        title=title,
        description="Existing day-based roadmap",
        total_days=2,
        daily_hours=1,
    )
    Day.objects.create(
        roadmap=roadmap,
        day_number=1,
        title="Legacy day one",
        estimated_hours=1,
        order=1,
        is_completed=True,
        completed_at=timezone.now(),
    )
    Day.objects.create(
        roadmap=roadmap,
        day_number=2,
        title="Legacy day two",
        estimated_hours=1,
        order=2,
    )
    return roadmap


class AdaptiveRoadmapServiceTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="adaptive-service-user",
            password="StrongPass123!",
        )
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        self.profile = create_complete_profile(self.user, self.pack)
        self.roadmap = create_roadmap(self.user)
        create_debugging_evidence(self.user)
        self.mission, _created, analysis = propose_next_mission(
            self.user,
            self.profile,
        )
        self.assertEqual(
            analysis.recommendation.dna.skill.code,
            "programming.debugging",
        )

    def propose(self):
        return propose_route_revision(
            self.user,
            self.roadmap,
            self.mission,
            self.profile,
        )[0]

    def test_initial_route_is_idempotent_and_preserves_legacy_days(self):
        before_days = list(
            self.roadmap.days.values_list(
                "id",
                "title",
                "is_completed",
            )
        )
        first, created = initialize_adaptive_route(
            self.user,
            self.roadmap,
            self.profile,
        )
        duplicate, duplicate_created = initialize_adaptive_route(
            self.user,
            self.roadmap,
            self.profile,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(first.status, "active")
        self.assertEqual(first.nodes.count(), self.pack.memberships.count())
        self.assertEqual(
            before_days,
            list(
                self.roadmap.days.values_list(
                    "id",
                    "title",
                    "is_completed",
                )
            ),
        )

    def test_proposal_moves_mission_without_moving_user_pinned_node(self):
        active, _ = initialize_adaptive_route(
            self.user,
            self.roadmap,
            self.profile,
        )
        pinned = active.nodes.get(skill__code="python.syntax_types")
        pinned_order = pinned.order
        toggle_node_lock(self.user, self.roadmap, pinned)
        proposal = self.propose()
        target_before = active.nodes.get(skill=self.mission.primary_skill)
        target_after = proposal.nodes.get(skill=self.mission.primary_skill)
        pinned_after = proposal.nodes.get(skill=pinned.skill)
        self.assertLess(target_after.order, target_before.order)
        self.assertEqual(pinned_after.order, pinned_order)
        self.assertTrue(pinned_after.is_user_locked)
        self.assertEqual(target_after.mission, self.mission)
        diff = build_revision_diff(active, proposal)
        self.assertGreater(diff.changed_count, 0)
        self.assertIn(
            target_after,
            [item.node for item in diff.changed_items],
        )

    def test_accept_is_atomic_and_keeps_legacy_days(self):
        proposal = self.propose()
        legacy_ids = list(self.roadmap.days.values_list("id", flat=True))
        accepted = accept_revision(self.user, self.roadmap, proposal)
        accepted.refresh_from_db()
        proposal.based_on.refresh_from_db()
        self.mission.refresh_from_db()
        self.assertEqual(accepted.status, "active")
        self.assertEqual(proposal.based_on.status, "superseded")
        self.assertEqual(self.mission.status, "accepted")
        self.assertEqual(
            accepted.nodes.get(mission=self.mission).status,
            "active",
        )
        self.assertEqual(
            legacy_ids,
            list(self.roadmap.days.values_list("id", flat=True)),
        )
        with self.assertRaises(ValidationError):
            accept_revision(self.user, self.roadmap, proposal)

    def test_reject_records_decision_and_blocks_same_snapshot(self):
        proposal = self.propose()
        original_active = proposal.based_on
        reject_revision(self.user, self.roadmap, proposal)
        proposal.refresh_from_db()
        original_active.refresh_from_db()
        self.mission.refresh_from_db()
        self.assertEqual(proposal.status, "rejected")
        self.assertEqual(original_active.status, "active")
        self.assertEqual(self.mission.status, "skipped")
        with self.assertRaisesRegex(ValidationError, "already declined"):
            propose_next_mission(self.user, self.profile)

    def test_postpone_and_resume_preserve_active_revision(self):
        proposal = self.propose()
        original_active = proposal.based_on
        postponed = postpone_revision(
            self.user,
            self.roadmap,
            proposal,
            days=7,
        )
        postponed.refresh_from_db()
        self.mission.refresh_from_db()
        self.assertEqual(postponed.status, "postponed")
        self.assertGreater(
            postponed.postponed_until,
            timezone.now() + timedelta(days=6),
        )
        self.assertEqual(self.mission.status, "postponed")
        original_active.refresh_from_db()
        self.assertEqual(original_active.status, "active")
        with self.assertRaisesRegex(ValidationError, "postponed"):
            toggle_node_lock(
                self.user,
                self.roadmap,
                original_active.nodes.get(skill__code="python.syntax_types"),
            )
        resumed = resume_revision(self.user, self.roadmap, postponed)
        resumed.refresh_from_db()
        self.mission.refresh_from_db()
        self.assertEqual(resumed.status, "proposed")
        self.assertIsNone(resumed.postponed_until)
        self.assertEqual(self.mission.status, "proposed")

    def test_restore_creates_new_revision_and_preserves_history(self):
        original, _ = initialize_adaptive_route(
            self.user,
            self.roadmap,
            self.profile,
        )
        original_pin = original.nodes.get(skill__code="python.syntax_types")
        toggle_node_lock(self.user, self.roadmap, original_pin)
        proposal = self.propose()
        accept_revision(self.user, self.roadmap, proposal)
        restored = restore_revision(self.user, self.roadmap, original)
        original.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(restored.revision_number, 3)
        self.assertEqual(restored.status, "active")
        self.assertEqual(restored.based_on, original)
        self.assertEqual(original.status, "superseded")
        self.assertEqual(proposal.status, "superseded")
        self.assertTrue(
            restored.nodes.get(skill__code="python.syntax_types").is_user_locked
        )

    def test_stale_mission_and_mismatched_roadmap_are_rejected(self):
        SkillState.objects.filter(
            user=self.user,
            skill=self.mission.primary_skill,
        ).update(mastery=Decimal("0.9500"), confidence=Decimal("0.9500"))
        with self.assertRaisesRegex(ValidationError, "stale"):
            self.propose()

        ml_roadmap = create_roadmap(
            self.user,
            topic="ML",
            title="Wrong-domain roadmap",
        )
        with self.assertRaisesRegex(ValidationError, "matches"):
            initialize_adaptive_route(
                self.user,
                ml_roadmap,
                self.profile,
            )

    def test_owner_scope_and_single_active_constraint_are_enforced(self):
        active, _ = initialize_adaptive_route(
            self.user,
            self.roadmap,
            self.profile,
        )
        other = User.objects.create_user(
            username="adaptive-service-other",
            password="StrongPass123!",
        )
        with self.assertRaises(Roadmap.DoesNotExist):
            initialize_adaptive_route(other, self.roadmap, self.profile)
        duplicate = RoadmapRevision(
            roadmap=self.roadmap,
            revision_number=99,
            status="active",
            reason_code="initial_skill_route",
            summary="Invalid duplicate active revision",
            input_state_version="x" * 64,
            input_state_at=timezone.now(),
            algorithm_version=ROUTE_ALGORITHM_VERSION,
        )
        with self.assertRaises(ValidationError):
            duplicate.save()
        self.assertEqual(active.status, "active")

    def test_route_models_are_registered_and_engine_has_no_ai_dependency(self):
        self.assertIn(RoadmapRevision, admin.site._registry)
        self.assertIn(RoadmapNode, admin.site._registry)
        source = (
            Path(__file__).resolve().parent
            / "services"
            / "adaptive_roadmaps.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Gemini", source)
        self.assertNotIn("ai_tools", source)


class AdaptiveRoadmapViewTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="adaptive-view-user",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="adaptive-view-other",
            password="StrongPass123!",
        )
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        self.profile = create_complete_profile(self.user, self.pack)
        self.roadmap = create_roadmap(self.user)
        create_debugging_evidence(self.user)
        self.mission, _created, _analysis = propose_next_mission(
            self.user,
            self.profile,
        )
        self.client.force_login(self.user)

    def create_proposal(self):
        response = self.client.post(
            reverse("intelligence:create_route_proposal"),
            {"mission": self.mission.id, "roadmap": self.roadmap.id},
        )
        self.assertEqual(response.status_code, 302)
        return RoadmapRevision.objects.get(
            roadmap=self.roadmap,
            status="proposed",
        )

    def test_routes_page_and_legacy_roadmap_link_render(self):
        routes = self.client.get(reverse("intelligence:adaptive_routes"))
        self.assertEqual(routes.status_code, 200)
        self.assertContains(routes, "Your route changes only when you say yes")
        self.assertContains(routes, self.roadmap.title)
        legacy = self.client.get(
            reverse("learning:roadmap_detail", args=[self.roadmap.id])
        )
        self.assertEqual(legacy.status_code, 200)
        self.assertContains(legacy, "Add adaptive route")

    def test_initialize_and_proposal_endpoints_require_post(self):
        initialize_url = reverse(
            "intelligence:initialize_route",
            args=[self.roadmap.id],
        )
        self.assertEqual(self.client.get(initialize_url).status_code, 405)
        response = self.client.post(initialize_url)
        self.assertRedirects(
            response,
            reverse(
                "intelligence:adaptive_route_detail",
                args=[self.roadmap.id],
            ),
        )
        self.assertTrue(
            RoadmapRevision.objects.filter(
                roadmap=self.roadmap,
                status="active",
            ).exists()
        )
        self.assertEqual(
            self.client.get(reverse("intelligence:create_route_proposal")).status_code,
            405,
        )

    def test_proposal_page_shows_diff_and_accepts_only_by_post(self):
        proposal = self.create_proposal()
        detail_url = reverse(
            "intelligence:adaptive_route_detail",
            args=[self.roadmap.id],
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Exact route difference")
        self.assertContains(detail, self.mission.title)
        accept_url = reverse(
            "intelligence:accept_revision",
            args=[self.roadmap.id, proposal.id],
        )
        self.assertEqual(self.client.get(accept_url).status_code, 405)
        response = self.client.post(accept_url)
        self.assertRedirects(response, detail_url)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "active")
        self.assertEqual(self.roadmap.days.count(), 2)

    def test_all_route_decisions_and_pins_are_post_only(self):
        active, _ = initialize_adaptive_route(
            self.user,
            self.roadmap,
            self.profile,
        )
        node = active.nodes.get(skill__code="python.syntax_types")
        pin_url = reverse(
            "intelligence:toggle_route_node_lock",
            args=[self.roadmap.id, node.id],
        )
        self.assertEqual(self.client.get(pin_url).status_code, 405)
        proposal = self.create_proposal()
        route_names = (
            "intelligence:reject_revision",
            "intelligence:postpone_revision",
            "intelligence:resume_revision",
            "intelligence:restore_route_revision",
        )
        for route_name in route_names:
            with self.subTest(route=route_name):
                url = reverse(
                    route_name,
                    args=[self.roadmap.id, proposal.id],
                )
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_invalid_postpone_fails_closed_without_mutation(self):
        proposal = self.create_proposal()
        response = self.client.post(
            reverse(
                "intelligence:postpone_revision",
                args=[self.roadmap.id, proposal.id],
            ),
            {"days": "999"},
        )
        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "proposed")

    def test_other_user_cannot_view_or_decide_route(self):
        proposal = self.create_proposal()
        self.client.force_login(self.other)
        detail = self.client.get(
            reverse(
                "intelligence:adaptive_route_detail",
                args=[self.roadmap.id],
            )
        )
        self.assertEqual(detail.status_code, 404)
        decision = self.client.post(
            reverse(
                "intelligence:accept_revision",
                args=[self.roadmap.id, proposal.id],
            )
        )
        self.assertEqual(decision.status_code, 404)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "proposed")

    def test_pack_change_invalidates_undecided_route_proposal(self):
        proposal = self.create_proposal()
        machine_learning = SkillPack.objects.get(
            code="machine_learning",
            version=1,
        )
        response = self.client.post(
            reverse("intelligence:onboarding"),
            {
                "primary_goal": "machine_learning",
                "custom_goal": "",
                "selected_pack": machine_learning.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.mission.refresh_from_db()
        self.assertEqual(proposal.status, "rejected")
        self.assertEqual(self.mission.status, "expired")

    def test_route_detail_query_count_is_bounded(self):
        self.create_proposal()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse(
                    "intelligence:adaptive_route_detail",
                    args=[self.roadmap.id],
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(queries),
            22,
            msg=f"Adaptive route detail exceeded query budget: {len(queries)}",
        )

    def test_account_export_contains_route_history_and_nodes(self):
        proposal = self.create_proposal()
        self.client.post(
            reverse(
                "intelligence:accept_revision",
                args=[self.roadmap.id, proposal.id],
            )
        )
        response = self.client.post(reverse("accounts:export_account_data"))
        self.assertEqual(response.status_code, 200)
        intelligence = json.loads(response.content)["learning_intelligence"]
        self.assertEqual(len(intelligence["roadmap_revisions"]), 2)
        self.assertEqual(
            len(intelligence["roadmap_nodes"]),
            self.pack.memberships.count() * 2,
        )


class FullStackRoadmapTests(TestCase):
    def test_fullstack_is_a_supported_deterministic_roadmap(self):
        seed_skill_packs()
        user = User.objects.create_user(
            username="fullstack-roadmap-user",
            password="StrongPass123!",
        )
        roadmap = RoadmapGenerator.generate_roadmap(
            user=user,
            topic="FULLSTACK",
            duration_months=1,
            daily_hours=1,
            level="beginner",
        )
        self.assertEqual(roadmap.get_topic_display(), "Django & Full-Stack")
        self.assertEqual(roadmap.days.count(), 30)
        self.assertIn(
            ("FULLSTACK", "Django & Full-Stack"),
            RoadmapCreateForm.TOPIC_CHOICES,
        )
        template = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / "learning"
            / "roadmap_create.html"
        ).read_text(encoding="utf-8")
        self.assertIn('data-topic="FULLSTACK"', template)
        pack = SkillPack.objects.get(code="django_fullstack", version=1)
        profile = create_complete_profile(user, pack)
        revision, created = initialize_adaptive_route(user, roadmap, profile)
        self.assertTrue(created)
        self.assertEqual(revision.nodes.count(), pack.memberships.count())
