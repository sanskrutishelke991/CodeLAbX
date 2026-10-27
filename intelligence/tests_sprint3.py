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

from .models import (
    LearnerIntelligenceProfile,
    Mission,
    Skill,
    SkillPack,
    SkillState,
)
from .services.evidence import record_learning_event
from .services.recommendations import (
    RECOMMENDATION_ALGORITHM_VERSION,
    analyze_learning_dna,
    propose_next_mission,
)
from .services.skill_packs import seed_skill_packs


def completed_profile(user, pack):
    now = timezone.now()
    return LearnerIntelligenceProfile.objects.create(
        user=user,
        primary_goal="placement",
        selected_pack=pack,
        routing_diagnostic_completed_at=now,
        goal_diagnostic_completed_at=now,
    )


def support_pack_skills(user, pack):
    now = timezone.now()
    for membership in pack.memberships.select_related("skill"):
        SkillState.objects.create(
            user=user,
            skill=membership.skill,
            mastery=Decimal("0.8500"),
            confidence=Decimal("0.8000"),
            freshness=Decimal("1.0000"),
            evidence_count=6,
            total_evidence_weight=Decimal("6.000"),
            last_evidence_at=now,
        )


class RecommendationEngineTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        self.user = User.objects.create_user(
            username="recommendation-user",
            password="StrongPass123!",
        )
        self.profile = completed_profile(self.user, self.pack)

    def test_same_goal_different_evidence_produces_different_missions(self):
        other = User.objects.create_user(
            username="recommendation-other",
            password="StrongPass123!",
        )
        other_profile = completed_profile(other, self.pack)
        support_pack_skills(self.user, self.pack)
        support_pack_skills(other, self.pack)

        functions = Skill.objects.get(code="python.functions")
        debugging = Skill.objects.get(code="programming.debugging")
        SkillState.objects.filter(user=self.user, skill=functions).update(
            mastery=Decimal("0.2000"),
            confidence=Decimal("0.8000"),
        )
        SkillState.objects.filter(user=other, skill=debugging).update(
            mastery=Decimal("0.2000"),
            confidence=Decimal("0.8000"),
        )

        first = analyze_learning_dna(self.user, self.profile)
        second = analyze_learning_dna(other, other_profile)
        self.assertEqual(first.recommendation.dna.skill, functions)
        self.assertEqual(second.recommendation.dna.skill, debugging)
        self.assertNotEqual(
            first.recommendation.dna.skill,
            second.recommendation.dna.skill,
        )

    def test_unmet_prerequisite_makes_advanced_skill_ineligible(self):
        analysis = analyze_learning_dna(self.user, self.profile)
        functions = next(
            candidate
            for candidate in analysis.candidates
            if candidate.dna.skill.code == "python.functions"
        )
        self.assertFalse(functions.eligible)
        self.assertIn("python.control_flow", functions.unmet_prerequisites)
        self.assertTrue(analysis.recommendation.eligible)

    def test_engine_is_domain_agnostic_across_all_starter_packs(self):
        for pack_code in ("machine_learning", "django_fullstack"):
            with self.subTest(pack=pack_code):
                user = User.objects.create_user(
                    username=f"domain-{pack_code}",
                    password="StrongPass123!",
                )
                pack = SkillPack.objects.get(code=pack_code, version=1)
                profile = completed_profile(user, pack)
                analysis = analyze_learning_dna(user, profile)
                pack_skill_ids = set(
                    pack.memberships.values_list("skill_id", flat=True)
                )
                self.assertEqual(
                    len(analysis.skills),
                    pack.memberships.count(),
                )
                self.assertIn(
                    analysis.recommendation.dna.skill.id,
                    pack_skill_ids,
                )
                self.assertTrue(analysis.recommendation.eligible)

    def test_unobserved_skill_does_not_expose_neutral_prior_as_mastery(self):
        analysis = analyze_learning_dna(self.user, self.profile)
        first = analysis.skills[0]
        self.assertIsNone(first.mastery)
        self.assertFalse(first.has_evidence)
        self.assertEqual(first.confidence, Decimal("0.0000"))
        self.assertIn("NO_EVIDENCE", analysis.recommendation.reason_codes)
        self.assertIn("LOW_CONFIDENCE", analysis.recommendation.reason_codes)

    def test_freshness_is_time_current_without_rewriting_snapshot(self):
        as_of = timezone.now()
        skill = Skill.objects.get(code="computing.computational_thinking")
        state = SkillState.objects.create(
            user=self.user,
            skill=skill,
            mastery=Decimal("0.7000"),
            confidence=Decimal("0.6000"),
            freshness=Decimal("1.0000"),
            evidence_count=2,
            total_evidence_weight=Decimal("2.000"),
            last_evidence_at=as_of,
        )
        later = as_of + timedelta(days=skill.default_half_life_days)
        analysis = analyze_learning_dna(self.user, self.profile, as_of=later)
        dna = next(item for item in analysis.skills if item.skill == skill)
        self.assertEqual(dna.freshness, Decimal("0.5000"))
        state.refresh_from_db()
        self.assertEqual(state.freshness, Decimal("1.0000"))

    def test_proposal_is_idempotent_and_supersedes_changed_snapshot(self):
        first, first_created, analysis = propose_next_mission(
            self.user,
            self.profile,
        )
        duplicate, duplicate_created, _ = propose_next_mission(
            self.user,
            self.profile,
        )
        self.assertTrue(first_created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(first.rationale["reason_codes"], list(
            analysis.recommendation.reason_codes
        ))
        self.assertLessEqual(first.additional_skills.count(), 2)

        SkillState.objects.create(
            user=self.user,
            skill=first.primary_skill,
            mastery=Decimal("0.9000"),
            confidence=Decimal("0.9000"),
            freshness=Decimal("1.0000"),
            evidence_count=10,
            total_evidence_weight=Decimal("10.000"),
            last_evidence_at=timezone.now(),
        )
        replacement, replacement_created, _ = propose_next_mission(
            self.user,
            self.profile,
        )
        self.assertTrue(replacement_created)
        self.assertNotEqual(first.id, replacement.id)
        first.refresh_from_db()
        self.assertEqual(first.status, "expired")
        self.assertEqual(replacement.status, "proposed")

    def test_mission_rejects_unbounded_or_non_object_rationale(self):
        skill = Skill.objects.get(code="computing.computational_thinking")
        mission = Mission(
            user=self.user,
            primary_skill=skill,
            mission_type="diagnostic",
            title="Bounded mission",
            description="A deterministic mission.",
            rationale={"large": "x" * 9000},
            success_criteria={},
            expected_minutes=15,
            recommendation_key="a" * 64,
        )
        with self.assertRaises(ValidationError):
            mission.save()
        mission.rationale = []
        with self.assertRaises(ValidationError):
            mission.save()

    def test_recommendation_engine_has_no_ai_dependency(self):
        service = (
            Path(__file__).resolve().parent
            / "services"
            / "recommendations.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Gemini", service)
        self.assertNotIn("ai_tools", service)
        self.assertEqual(
            RECOMMENDATION_ALGORITHM_VERSION,
            "prerequisite-priority-v1",
        )

    def test_mission_is_registered_in_admin(self):
        self.assertIn(Mission, admin.site._registry)


class LearningDNAViewTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        self.user = User.objects.create_user(
            username="dna-view-user",
            password="StrongPass123!",
        )
        self.profile = completed_profile(self.user, self.pack)
        self.skill = Skill.objects.get(code="programming.problem_decomposition")
        record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="assessment_answer",
            source_type="own_assessment",
            source_id="1",
            idempotency_key="dna-view-own-1",
            outcome=Decimal("1.0000"),
            evidence_weight=Decimal("1.000"),
        )
        self.client.force_login(self.user)

    def test_dna_and_legacy_baseline_routes_render_honest_profile(self):
        response = self.client.get(reverse("intelligence:dna"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This is how you learn.")
        self.assertContains(response, "Your evidence baseline")
        self.assertContains(response, "No scoreable evidence yet")
        self.assertContains(response, "XP never changes these numbers")
        self.assertEqual(
            len(response.context["analysis"].skills),
            self.pack.memberships.count(),
        )
        legacy = self.client.get(reverse("intelligence:baseline"))
        self.assertEqual(legacy.status_code, 200)
        self.assertContains(legacy, "Learning DNA")

    def test_evidence_explorer_is_owner_scoped_and_filterable(self):
        other = User.objects.create_user(
            username="evidence-private-other",
            password="StrongPass123!",
        )
        other_skill = Skill.objects.get(code="ml.neural_networks")
        record_learning_event(
            user=other,
            skill_code=other_skill.code,
            event_type="assessment_answer",
            source_type="private_other_source",
            source_id="secret",
            idempotency_key="private-other-event",
            outcome=Decimal("1.0000"),
        )
        response = self.client.get(
            reverse("intelligence:evidence"),
            {"skill": self.skill.code, "event_type": "assessment_answer"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.skill.name)
        self.assertContains(response, "own_assessment")
        self.assertNotContains(response, "private_other_source")
        self.assertNotContains(response, other_skill.name)

    def test_invalid_evidence_filter_fails_closed_without_error(self):
        response = self.client.get(
            reverse("intelligence:evidence"),
            {"skill": "unknown.skill", "event_type": "made_up"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A filter was not recognized")
        self.assertNotContains(response, "own_assessment")

    def test_recalculation_is_post_only_and_creates_owner_mission(self):
        url = reverse("intelligence:recalculate_recommendation")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("intelligence:dna"))
        mission = Mission.objects.get(user=self.user, status="proposed")
        self.assertEqual(mission.rationale["algorithm_version"], RECOMMENDATION_ALGORITHM_VERSION)
        self.assertEqual(Mission.objects.exclude(user=self.user).count(), 0)

    def test_account_export_includes_portable_intelligence_data(self):
        self.client.post(reverse("intelligence:recalculate_recommendation"))
        response = self.client.post(reverse("accounts:export_account_data"))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["learning_intelligence"]
        self.assertEqual(
            payload["profile"]["selected_pack__code"],
            self.pack.code,
        )
        self.assertEqual(
            payload["learning_events"][0]["skill__code"],
            self.skill.code,
        )
        self.assertEqual(len(payload["missions"]), 1)
        self.assertNotIn("idempotency_key", payload["learning_events"][0])
        self.assertNotIn("recommendation_key", payload["missions"][0])

    def test_incomplete_profile_cannot_open_dna_or_evidence(self):
        self.profile.goal_diagnostic_completed_at = None
        self.profile.save(update_fields=["goal_diagnostic_completed_at"])
        for route in ("intelligence:dna", "intelligence:evidence"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertRedirects(
                    response,
                    reverse("intelligence:diagnostic"),
                    fetch_redirect_response=False,
                )

    def test_dna_query_count_stays_bounded_by_pack_size(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("intelligence:dna"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(queries),
            15,
            msg=f"Learning DNA exceeded query budget: {len(queries)}",
        )
