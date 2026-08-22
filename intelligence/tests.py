from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.tasks.base import TaskResultStatus
from django.test import TestCase
from django.utils import timezone

from .models import (
    LearningEvent,
    Mission,
    RoadmapNode,
    RoadmapRevision,
    Skill,
    SkillPack,
    SkillPackMembership,
    SkillPrerequisite,
    SkillState,
)
from .services.evidence import record_learning_event
from .services.mastery import (
    ALGORITHM_VERSION,
    calculate_skill_state,
    rebuild_skill_state,
)
from .services.skill_packs import (
    seed_skill_packs,
    validate_skill_pack_directory,
)
from .tasks import rebuild_user_skill_states_task


class SkillPackValidationTests(TestCase):
    def test_default_three_domain_packs_and_shared_core_validate(self):
        validated = validate_skill_pack_directory()
        self.assertEqual(len(validated.packs), 4)
        self.assertEqual(len(validated.skills), 60)
        self.assertEqual(len(validated.memberships), 85)
        self.assertEqual(len(validated.prerequisites), 63)
        self.assertIn("programming_dsa", {pack["code"] for pack in validated.packs})
        self.assertIn("machine_learning", {pack["code"] for pack in validated.packs})
        self.assertIn("django_fullstack", {pack["code"] for pack in validated.packs})

    def test_check_only_does_not_write_database(self):
        summary = seed_skill_packs(check_only=True)
        self.assertEqual(summary["packs"], 4)
        self.assertFalse(Skill.objects.exists())
        self.assertFalse(SkillPack.objects.exists())

    def test_seed_is_idempotent_and_shared_skills_are_reused(self):
        first = seed_skill_packs()
        second = seed_skill_packs()
        self.assertEqual(first, second)
        self.assertEqual(SkillPack.objects.count(), 4)
        self.assertEqual(Skill.objects.count(), 60)
        self.assertEqual(SkillPackMembership.objects.count(), 85)
        self.assertEqual(SkillPrerequisite.objects.count(), 63)
        shared = Skill.objects.get(code="programming.problem_decomposition")
        self.assertGreaterEqual(shared.pack_memberships.count(), 4)

    def test_cycle_is_rejected_before_database_writes(self):
        payload = {
            "code": "cycle_pack",
            "name": "Cycle Pack",
            "description": "Invalid cyclic test pack.",
            "version": 1,
            "skills": [
                {
                    "code": "test.alpha",
                    "name": "Alpha",
                    "description": "Alpha skill.",
                    "domain": "test",
                },
                {
                    "code": "test.beta",
                    "name": "Beta",
                    "description": "Beta skill.",
                    "domain": "test",
                },
            ],
            "memberships": [
                {"skill": "test.alpha", "order": 1},
                {"skill": "test.beta", "order": 2},
            ],
            "prerequisites": [
                {"skill": "test.alpha", "requires": "test.beta"},
                {"skill": "test.beta", "requires": "test.alpha"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "cycle.json").write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValidationError, "cycle"):
                validate_skill_pack_directory(directory)
        self.assertFalse(Skill.objects.exists())


class LearningEvidenceTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="evidence-user",
            password="StrongPass123!",
        )
        self.skill = Skill.objects.get(code="programming.problem_decomposition")

    def test_event_write_is_idempotent_and_rebuilds_state(self):
        event, created, state = record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="diagnostic_answer",
            source_type="diagnostic",
            source_id="question-1",
            idempotency_key="diagnostic:question-1",
            outcome=1,
            difficulty=Decimal("0.6000"),
            evidence_weight=Decimal("1.100"),
            metadata={"misconception_codes": []},
        )
        duplicate, duplicate_created, duplicate_state = record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="diagnostic_answer",
            source_type="diagnostic",
            source_id="question-1",
            idempotency_key="diagnostic:question-1",
            outcome=0,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(event.id, duplicate.id)
        self.assertEqual(LearningEvent.objects.count(), 1)
        self.assertEqual(state.evidence_count, 1)
        self.assertEqual(duplicate_state.evidence_count, 1)

    def test_idempotency_collision_with_different_source_is_rejected(self):
        record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="lesson_complete",
            source_type="day",
            source_id="1",
            idempotency_key="shared-key",
            outcome=None,
            evidence_weight=Decimal("0.200"),
        )
        with self.assertRaisesRegex(ValidationError, "different event"):
            record_learning_event(
                user=self.user,
                skill_code=self.skill.code,
                event_type="lesson_complete",
                source_type="day",
                source_id="2",
                idempotency_key="shared-key",
                outcome=None,
            )

    def test_event_is_immutable_after_creation(self):
        event, _, _ = record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="self_report",
            source_type="onboarding",
            source_id="self-1",
            idempotency_key="self-report:1",
            outcome=Decimal("0.5000"),
            evidence_weight=Decimal("0.050"),
        )
        event.outcome = Decimal("1.0000")
        with self.assertRaisesRegex(ValidationError, "immutable"):
            event.save(update_fields=["outcome"])

    def test_metadata_and_numeric_boundaries_are_validated(self):
        with self.assertRaises(ValidationError):
            record_learning_event(
                user=self.user,
                skill_code=self.skill.code,
                event_type="self_report",
                source_type="onboarding",
                source_id="large",
                idempotency_key="large-metadata",
                outcome=1,
                metadata={"value": "x" * 5000},
            )
        with self.assertRaises(ValidationError):
            record_learning_event(
                user=self.user,
                skill_code=self.skill.code,
                event_type="self_report",
                source_type="onboarding",
                source_id="bad-outcome",
                idempotency_key="bad-outcome",
                outcome=2,
            )


class MasteryEngineTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="mastery-user",
            password="StrongPass123!",
        )
        self.skill = Skill.objects.get(code="python.functions")

    def test_empty_state_uses_neutral_prior_and_zero_confidence(self):
        calculated = calculate_skill_state([], self.skill)
        self.assertEqual(calculated.mastery, Decimal("0.5000"))
        self.assertEqual(calculated.confidence, Decimal("0.0000"))
        self.assertEqual(calculated.freshness, Decimal("0.0000"))
        self.assertEqual(calculated.evidence_count, 0)

    def test_half_life_produces_half_freshness(self):
        as_of = timezone.now()
        event = LearningEvent(
            user=self.user,
            skill=self.skill,
            event_type="assessment_answer",
            source_type="assessment",
            source_id="1",
            idempotency_key="half-life",
            outcome=Decimal("1.0000"),
            difficulty=Decimal("0.5000"),
            evidence_weight=Decimal("1.000"),
            occurred_at=as_of
            - timedelta(days=self.skill.default_half_life_days),
        )
        calculated = calculate_skill_state([event], self.skill, as_of=as_of)
        self.assertEqual(calculated.freshness, Decimal("0.5000"))

    def test_hints_reduce_weight_without_invalid_scores(self):
        now = timezone.now()
        clean = LearningEvent(
            user=self.user,
            skill=self.skill,
            event_type="assessment_answer",
            source_type="assessment",
            source_id="clean",
            idempotency_key="clean",
            outcome=Decimal("1.0000"),
            evidence_weight=Decimal("1.000"),
            occurred_at=now,
        )
        hinted = LearningEvent(
            user=self.user,
            skill=self.skill,
            event_type="assessment_answer",
            source_type="assessment",
            source_id="hinted",
            idempotency_key="hinted",
            outcome=Decimal("1.0000"),
            evidence_weight=Decimal("1.000"),
            hints_used=5,
            occurred_at=now,
        )
        clean_state = calculate_skill_state([clean], self.skill, as_of=now)
        hinted_state = calculate_skill_state([hinted], self.skill, as_of=now)
        self.assertGreater(clean_state.confidence, hinted_state.confidence)
        for value in (
            clean_state.mastery,
            clean_state.confidence,
            clean_state.freshness,
            hinted_state.mastery,
            hinted_state.confidence,
            hinted_state.freshness,
        ):
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)

    def test_database_rebuild_is_deterministic_and_records_misconceptions(self):
        occurred_at = timezone.now()
        record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="assessment_answer",
            source_type="assessment",
            source_id="q1",
            idempotency_key="assessment:q1",
            outcome=Decimal("0.2000"),
            evidence_weight=Decimal("1.000"),
            metadata={"misconception_codes": ["FUNCTION_RETURN"]},
            occurred_at=occurred_at,
            recalculate=False,
        )
        first = rebuild_skill_state(self.user, self.skill, as_of=occurred_at)
        values = (
            first.mastery,
            first.confidence,
            first.freshness,
            first.total_evidence_weight,
        )
        second = rebuild_skill_state(self.user, self.skill, as_of=occurred_at)
        self.assertEqual(
            values,
            (
                second.mastery,
                second.confidence,
                second.freshness,
                second.total_evidence_weight,
            ),
        )
        self.assertEqual(second.misconception_codes, ["FUNCTION_RETURN"])
        self.assertEqual(second.algorithm_version, ALGORITHM_VERSION)

    def test_numeric_engine_has_no_ai_dependency(self):
        source = Path(
            __file__
        ).resolve().parent / "services" / "mastery.py"
        content = source.read_text(encoding="utf-8")
        self.assertNotIn("Gemini", content)
        self.assertNotIn("ai_tools", content)


class IntelligenceOperationsTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="intelligence-ops-user",
            password="StrongPass123!",
        )
        self.skill = Skill.objects.get(code="programming.debugging")
        record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="diagnostic_answer",
            source_type="diagnostic",
            source_id="debug-1",
            idempotency_key="debug-1",
            outcome=1,
            recalculate=False,
        )

    def test_seed_and_rebuild_commands(self):
        call_command("seed_skill_packs", check_only=True, verbosity=0)
        SkillState.objects.all().delete()
        call_command(
            "rebuild_skill_states",
            user_id=self.user.id,
            verbosity=0,
        )
        self.assertTrue(
            SkillState.objects.filter(user=self.user, skill=self.skill).exists()
        )

    @patch("intelligence.tasks.rebuild_user_skill_states")
    def test_task_contract_returns_json_safe_summary(self, rebuild):
        rebuild.return_value = [object(), object()]
        result = rebuild_user_skill_states_task.enqueue(user_id=self.user.id)
        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        self.assertEqual(
            result.return_value,
            {"user_id": self.user.id, "states_rebuilt": 2},
        )

    def test_all_operational_models_are_registered_in_admin(self):
        for model in (
            SkillPack,
            Skill,
            SkillPackMembership,
            SkillPrerequisite,
            LearningEvent,
            SkillState,
            Mission,
            RoadmapRevision,
            RoadmapNode,
        ):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_database_enforces_unique_event_key(self):
        LearningEvent.objects.create(
            user=self.user,
            skill=self.skill,
            event_type="diagnostic_answer",
            source_type="diagnostic",
            source_id="unique-1",
            idempotency_key="unique-key",
            outcome=Decimal("1.0000"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LearningEvent.objects.bulk_create(
                    [
                        LearningEvent(
                            user=self.user,
                            skill=self.skill,
                            event_type="diagnostic_answer",
                            source_type="diagnostic",
                            source_id="unique-2",
                            idempotency_key="unique-key",
                            outcome=Decimal("0.0000"),
                        )
                    ]
                )
