from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from assessments.models import Test, TestAttempt
from challenges.models import Challenge, UserChallenge
from learning.models import Day, Roadmap
from practice.models import CodeReview

from .models import (
    DiagnosticAttempt,
    DiagnosticResponse,
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    SkillPack,
    SkillState,
)
from .services.diagnostics import load_diagnostic
from .services.emitters import (
    emit_assessment_attempt,
    emit_challenge_attempt,
    emit_code_review,
    emit_day_completion,
)
from .services.skill_packs import seed_skill_packs


class DiagnosticFlowTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="diagnostic-user",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)
        self.pack = SkillPack.objects.get(
            code="programming_dsa",
            version=1,
        )

    def onboard(self):
        return self.client.post(
            reverse("intelligence:onboarding"),
            {
                "primary_goal": "placement",
                "custom_goal": "",
                "selected_pack": self.pack.id,
            },
        )

    def submit_current_with_correct_answers(self):
        profile = LearnerIntelligenceProfile.objects.get(user=self.user)
        attempt = DiagnosticAttempt.objects.get(
            user=self.user,
            status="started",
        )
        definition = load_diagnostic(attempt.stage, profile)
        payload = {
            "attempt_id": attempt.id,
            **{
                f"answer_{question['id']}": question["correct"]
                for question in definition.questions
            },
        }
        return self.client.post(
            reverse("intelligence:diagnostic_submit"),
            payload,
        )

    def test_complete_two_stage_flow_creates_evidence_and_baseline(self):
        self.assertEqual(self.onboard().status_code, 302)
        routing_page = self.client.get(reverse("intelligence:diagnostic"))
        self.assertEqual(routing_page.status_code, 200)
        self.assertEqual(routing_page.context["attempt"].stage, "routing")
        for question in routing_page.context["questions"]:
            self.assertNotIn("correct", question)

        routing_response = self.submit_current_with_correct_answers()
        self.assertRedirects(
            routing_response,
            reverse("intelligence:diagnostic"),
        )
        goal_page = self.client.get(reverse("intelligence:diagnostic"))
        self.assertEqual(goal_page.context["attempt"].stage, "goal")
        goal_response = self.submit_current_with_correct_answers()
        self.assertRedirects(
            goal_response,
            reverse("intelligence:dna"),
        )

        profile = LearnerIntelligenceProfile.objects.get(user=self.user)
        self.assertTrue(profile.diagnostics_complete)
        self.assertEqual(DiagnosticAttempt.objects.filter(user=self.user).count(), 2)
        self.assertEqual(DiagnosticResponse.objects.filter(attempt__user=self.user).count(), 17)
        self.assertEqual(LearningEvent.objects.filter(user=self.user).count(), 17)
        self.assertEqual(SkillState.objects.filter(user=self.user).count(), 17)
        baseline = self.client.get(reverse("intelligence:baseline"))
        self.assertEqual(baseline.status_code, 200)
        self.assertContains(baseline, "Your evidence baseline")
        self.assertContains(baseline, "Confidence")
        self.assertContains(baseline, "Freshness")
        self.assertEqual(
            Mission.objects.filter(user=self.user, status="proposed").count(),
            1,
        )

    def test_incomplete_submission_is_rejected_without_partial_rows(self):
        self.onboard()
        self.client.get(reverse("intelligence:diagnostic"))
        attempt = DiagnosticAttempt.objects.get(user=self.user)
        response = self.client.post(
            reverse("intelligence:diagnostic_submit"),
            {"attempt_id": attempt.id},
        )
        self.assertEqual(response.status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "started")
        self.assertFalse(DiagnosticResponse.objects.exists())
        self.assertFalse(LearningEvent.objects.exists())

    def test_other_user_cannot_submit_attempt(self):
        self.onboard()
        self.client.get(reverse("intelligence:diagnostic"))
        attempt = DiagnosticAttempt.objects.get(user=self.user)
        other = User.objects.create_user(
            username="diagnostic-other",
            password="StrongPass123!",
        )
        self.client.force_login(other)
        response = self.client.post(
            reverse("intelligence:diagnostic_submit"),
            {"attempt_id": attempt.id, "answer_any": 0},
        )
        self.assertEqual(response.status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "started")

    def test_pack_change_resets_started_diagnostic(self):
        self.onboard()
        self.client.get(reverse("intelligence:diagnostic"))
        self.assertTrue(
            DiagnosticAttempt.objects.filter(user=self.user, status="started").exists()
        )
        ml_pack = SkillPack.objects.get(code="machine_learning", version=1)
        response = self.client.post(
            reverse("intelligence:onboarding"),
            {
                "primary_goal": "machine_learning",
                "custom_goal": "",
                "selected_pack": ml_pack.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            DiagnosticAttempt.objects.filter(user=self.user, status="started").exists()
        )
        profile = LearnerIntelligenceProfile.objects.get(user=self.user)
        self.assertEqual(profile.selected_pack, ml_pack)
        self.assertFalse(profile.diagnostics_complete)


class ExistingWorkflowEmitterTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="emitter-user",
            password="StrongPass123!",
        )

    def execute_commit_callbacks(self, callback):
        with self.captureOnCommitCallbacks(execute=True):
            callback()

    def test_day_challenge_review_and_assessment_emit_idempotent_events(self):
        roadmap = Roadmap.objects.create(
            user=self.user,
            topic="DSA",
            title="Emitter roadmap",
            total_days=1,
            daily_hours=1,
        )
        day = Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title="Arrays and strings",
            description="Practice array traversal",
            estimated_hours=1,
            order=1,
            is_completed=True,
        )
        challenge = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="theory",
            difficulty="medium",
            title="Graph traversal",
            description="Which structure does BFS use?",
            options=[{"text": "Queue"}, {"text": "Stack"}],
            correct_option=0,
        )
        challenge_attempt = UserChallenge.objects.create(
            user=self.user,
            challenge=challenge,
            status="completed",
            selected_option=0,
            is_correct=True,
            evaluation_type="deterministic",
            time_taken_seconds=20,
            completed_at=timezone.now(),
        )
        review = CodeReview.objects.create(
            user=self.user,
            language="python",
            code_hash=CodeReview.hash_code("python", "print(1)"),
        )
        test = Test.objects.create(
            user=self.user,
            title="Functions test",
            topic="Python functions",
            status="completed",
            questions=[
                {
                    "question": "What does return do?",
                    "options": ["Exits with a value", "Imports a module"],
                    "correct": 0,
                }
            ],
            score=100,
            completed_at=timezone.now(),
        )
        assessment_attempt = TestAttempt.objects.create(
            test=test,
            user=self.user,
            answers={"0": 0},
            score=100,
            time_taken_seconds=30,
            completed_at=timezone.now(),
            is_finalized=True,
        )

        self.execute_commit_callbacks(lambda: emit_day_completion(self.user, day))
        self.execute_commit_callbacks(
            lambda: emit_challenge_attempt(self.user, challenge_attempt)
        )
        self.execute_commit_callbacks(
            lambda: emit_code_review(
                self.user,
                review,
                language="python",
                problem="Debug a function",
            )
        )
        self.execute_commit_callbacks(
            lambda: emit_assessment_attempt(
                self.user,
                test,
                assessment_attempt,
            )
        )
        self.execute_commit_callbacks(lambda: emit_day_completion(self.user, day))

        events = LearningEvent.objects.filter(user=self.user)
        self.assertEqual(events.count(), 4)
        self.assertCountEqual(
            events.values_list("event_type", flat=True),
            [
                "lesson_complete",
                "challenge_answer",
                "ai_review",
                "assessment_answer",
            ],
        )
        self.assertEqual(
            SkillState.objects.filter(user=self.user).count(),
            4,
        )

    def test_missing_skill_is_logged_and_does_not_break_source_flow(self):
        SkillState.objects.all().delete()
        from .services import emitters

        with patch.object(
            emitters,
            "infer_skill_code",
            return_value="missing.skill",
        ):
            with self.assertLogs("intelligence.services.emitters", level="WARNING"):
                self.execute_commit_callbacks(
                    lambda: emitters._enqueue_after_commit(
                        user=self.user,
                        skill_code="missing.skill",
                        event_type="lesson_complete",
                        source_type="day",
                        source_id="missing",
                        idempotency_key="missing",
                        outcome=None,
                    )
                )
        self.assertFalse(LearningEvent.objects.filter(user=self.user).exists())
