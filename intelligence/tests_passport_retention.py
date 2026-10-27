from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import (
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    Skill,
    SkillPack,
    SkillState,
)
from .services.evidence import record_learning_event
from .services.mastery import rebuild_skill_state
from .services.passport import build_skill_passport
from .services.retention import (
    RETENTION_ALGORITHM_VERSION,
    analyze_retention,
    create_retention_mission,
)
from .services.skill_packs import seed_skill_packs


def complete_profile(user, pack):
    now = timezone.now()
    return LearnerIntelligenceProfile.objects.create(
        user=user,
        primary_goal="placement",
        selected_pack=pack,
        routing_diagnostic_completed_at=now,
        goal_diagnostic_completed_at=now,
    )


def record_event(user, skill, index, *, event_type, outcome, occurred_at):
    return record_learning_event(
        user=user,
        skill_code=skill.code,
        event_type=event_type,
        source_type=f"wave-source-{event_type}",
        source_id=f"{skill.id}:{index}",
        idempotency_key=f"passport-retention:{skill.id}:{index}",
        outcome=outcome,
        evidence_weight=Decimal("1.000"),
        occurred_at=occurred_at,
        recalculate=False,
    )[0]


def create_stale_supported_skill(user, skill, *, as_of):
    occurred_at = as_of - timedelta(days=skill.default_half_life_days * 2)
    for index, event_type in enumerate(
        (
            "diagnostic_answer",
            "assessment_answer",
            "challenge_answer",
        )
    ):
        record_event(
            user,
            skill,
            index,
            event_type=event_type,
            outcome=Decimal("1.0000"),
            occurred_at=occurred_at,
        )
    record_event(
        user,
        skill,
        3,
        event_type="self_report",
        outcome=Decimal("0.8000"),
        occurred_at=occurred_at,
    )
    record_event(
        user,
        skill,
        4,
        event_type="ai_review",
        outcome=None,
        occurred_at=as_of,
    )
    record_event(
        user,
        skill,
        5,
        event_type="lesson_complete",
        outcome=None,
        occurred_at=as_of,
    )
    return rebuild_skill_state(user, skill, as_of=as_of)


class SkillPassportTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="passport-user",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="passport-other",
            password="StrongPass123!",
        )
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        self.profile = complete_profile(self.user, self.pack)
        self.skill = Skill.objects.get(code="programming.debugging")
        self.as_of = timezone.now()
        self.state = create_stale_supported_skill(
            self.user,
            self.skill,
            as_of=self.as_of,
        )

    def test_passport_separates_deterministic_supporting_and_observed_records(self):
        passport = build_skill_passport(
            self.user,
            self.profile,
            as_of=self.as_of,
        )
        item = next(
            value for value in passport.skills if value.dna.skill == self.skill
        )
        self.assertEqual(item.total_event_count, 6)
        self.assertEqual(item.scoreable_event_count, 4)
        self.assertEqual(item.deterministic_event_count, 3)
        self.assertEqual(item.supporting_scoreable_count, 1)
        self.assertEqual(item.observed_only_count, 2)
        self.assertEqual(item.dna.evidence_count, 4)
        self.assertEqual(passport.deterministic_event_count, 3)
        self.assertEqual(passport.observed_only_count, 2)
        self.assertNotIn("verified", item.evidence_level.lower())

    def test_other_users_evidence_never_enters_passport(self):
        record_learning_event(
            user=self.other,
            skill_code=self.skill.code,
            event_type="assessment_answer",
            source_type="OTHER_USER_PRIVATE_SOURCE",
            source_id="other",
            idempotency_key="other-private-passport-event",
            outcome=Decimal("1.0000"),
        )
        passport = build_skill_passport(self.user, self.profile)
        item = next(
            value for value in passport.skills if value.dna.skill == self.skill
        )
        self.assertEqual(item.total_event_count, 6)
        self.assertNotIn(
            "OTHER_USER_PRIVATE_SOURCE",
            [source.event_type for source in item.sources],
        )

    def test_passport_is_domain_agnostic_for_all_starter_packs(self):
        for code in ("machine_learning", "django_fullstack"):
            with self.subTest(pack=code):
                user = User.objects.create_user(
                    username=f"passport-{code}",
                    password="StrongPass123!",
                )
                pack = SkillPack.objects.get(code=code, version=1)
                profile = complete_profile(user, pack)
                passport = build_skill_passport(user, profile)
                self.assertEqual(
                    len(passport.skills),
                    pack.memberships.count(),
                )
                self.assertEqual(passport.observed_skill_count, 0)

    def test_private_passport_page_uses_honest_language_and_owner_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("intelligence:passport"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evidence observed—not independently verified")
        self.assertContains(response, self.skill.name)
        self.assertContains(response, "Deterministic: 3")
        self.assertNotContains(response, "Verified skill")
        self.assertNotContains(response, "OTHER_USER_PRIVATE_SOURCE")
        self.client.logout()
        anonymous = self.client.get(reverse("intelligence:passport"))
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn(reverse("accounts:login"), anonymous.url)

    def test_passport_query_count_is_bounded(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("intelligence:passport"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(queries),
            13,
            msg=f"Skill Passport exceeded query budget: {len(queries)}",
        )


class RetentionMissionTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="retention-user",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="retention-other",
            password="StrongPass123!",
        )
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        self.profile = complete_profile(self.user, self.pack)
        self.other_profile = complete_profile(self.other, self.pack)
        self.skill = Skill.objects.get(code="programming.debugging")
        self.as_of = timezone.now()
        self.state = create_stale_supported_skill(
            self.user,
            self.skill,
            as_of=self.as_of,
        )

    def test_analysis_selects_stale_supported_skill_without_decaying_mastery(self):
        original_mastery = self.state.mastery
        analysis = analyze_retention(
            self.user,
            self.profile,
            as_of=self.as_of,
        )
        candidate = next(
            item for item in analysis.candidates if item.dna.skill == self.skill
        )
        self.assertEqual(candidate.dna.freshness, Decimal("0.2500"))
        self.assertEqual(candidate.urgency, "urgent")
        self.assertEqual(candidate.recommended_checks, 4)
        self.assertEqual(
            candidate.days_since_evidence,
            self.skill.default_half_life_days * 2,
        )
        self.state.refresh_from_db()
        self.assertEqual(self.state.mastery, original_mastery)

    def test_fresh_and_low_mastery_skills_are_not_retention_candidates(self):
        fresh = Skill.objects.get(code="python.syntax_types")
        for index in range(3):
            record_event(
                self.user,
                fresh,
                20 + index,
                event_type="assessment_answer",
                outcome=Decimal("1.0000"),
                occurred_at=self.as_of,
            )
        rebuild_skill_state(self.user, fresh, as_of=self.as_of)

        weak = Skill.objects.get(code="python.control_flow")
        old = self.as_of - timedelta(days=weak.default_half_life_days * 2)
        for index in range(4):
            record_event(
                self.user,
                weak,
                30 + index,
                event_type="assessment_answer",
                outcome=Decimal("0.0000"),
                occurred_at=old,
            )
        rebuild_skill_state(self.user, weak, as_of=self.as_of)

        candidates = analyze_retention(
            self.user,
            self.profile,
            as_of=self.as_of,
        ).candidates
        codes = {item.dna.skill.code for item in candidates}
        self.assertNotIn(fresh.code, codes)
        self.assertNotIn(weak.code, codes)
        self.assertIn(self.skill.code, codes)

    def test_refresh_mission_is_deterministic_idempotent_and_honest(self):
        original_mastery = self.state.mastery
        mission, created, candidate = create_retention_mission(
            self.user,
            self.profile,
            self.skill,
            as_of=self.as_of,
        )
        duplicate, duplicate_created, _ = create_retention_mission(
            self.user,
            self.profile,
            self.skill,
            as_of=self.as_of,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(mission.id, duplicate.id)
        self.assertEqual(mission.mission_type, "retention")
        self.assertEqual(mission.status, "proposed")
        self.assertEqual(
            mission.rationale["algorithm_version"],
            RETENTION_ALGORITHM_VERSION,
        )
        self.assertEqual(mission.rationale["freshness"], "0.2500")
        self.assertEqual(
            mission.success_criteria["minimum_scoreable_events"],
            candidate.recommended_checks,
        )
        self.assertIn("does not lower", mission.description)
        self.state.refresh_from_db()
        self.assertEqual(self.state.mastery, original_mastery)

    def test_existing_current_mission_blocks_new_refresh_proposal(self):
        Mission.objects.create(
            user=self.user,
            primary_skill=self.skill,
            mission_type="practice",
            status="proposed",
            title="Current mission",
            description="An already proposed mission.",
            rationale={"reason": "test"},
            success_criteria={"rule": "test"},
            expected_minutes=20,
            recommendation_key="b" * 64,
        )
        with self.assertRaisesRegex(ValidationError, "Current mission"):
            create_retention_mission(
                self.user,
                self.profile,
                self.skill,
                as_of=self.as_of,
            )
        self.assertEqual(Mission.objects.filter(user=self.user).count(), 1)

    def test_refresh_endpoint_is_post_only_pack_scoped_and_owner_scoped(self):
        self.client.force_login(self.user)
        url = reverse(
            "intelligence:create_refresh_mission",
            args=[self.skill.id],
        )
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("intelligence:retention"))
        mission = Mission.objects.get(user=self.user, mission_type="retention")

        outside_skill = Skill.objects.get(code="ml.neural_networks")
        outside_url = reverse(
            "intelligence:create_refresh_mission",
            args=[outside_skill.id],
        )
        self.assertEqual(self.client.post(outside_url).status_code, 404)

        self.client.force_login(self.other)
        other_attempt = self.client.post(url)
        self.assertEqual(other_attempt.status_code, 302)
        self.assertFalse(
            Mission.objects.filter(user=self.other, mission_type="retention").exists()
        )
        self.assertTrue(Mission.objects.filter(id=mission.id).exists())

    def test_retention_page_is_private_and_query_bounded(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("intelligence:retention"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Refresh evidence without erasing mastery")
        self.assertContains(response, self.skill.name)
        self.assertLessEqual(
            len(queries),
            14,
            msg=f"Retention Center exceeded query budget: {len(queries)}",
        )

    def test_retention_engine_has_no_ai_dependency(self):
        source = (
            Path(__file__).resolve().parent
            / "services"
            / "retention.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Gemini", source)
        self.assertNotIn("ai_tools", source)
        self.assertNotIn("progress.models", source)
