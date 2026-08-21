import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from progress.models import UserLevel, XPTransaction

from .models import Challenge, ChallengeStreak, UserChallenge


@override_settings(AI_FEATURES_ENABLED=False)
class ChallengeRewardIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="challenge-xp-user", password="StrongPass123!")
        self.client.force_login(self.user)

    def test_theory_challenge_reward_is_awarded_once(self):
        challenge = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="theory",
            difficulty="easy",
            title="Question",
            description="Choose zero",
            options=[{"text": "A"}, {"text": "B"}],
            correct_option=0,
            xp_reward=20,
        )
        url = reverse("challenges:submit", args=[challenge.id])
        payload = json.dumps({"selected_option": 0, "time_taken": 10})
        first = self.client.post(url, data=payload, content_type="application/json")
        second = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["xp_earned"], 20)
        self.assertEqual(second.json()["xp_earned"], 0)
        self.assertTrue(second.json()["already_completed"])
        self.assertEqual(UserLevel.objects.get(user=self.user).total_xp_earned, 20)
        self.assertEqual(XPTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserChallenge.objects.filter(user=self.user).count(), 1)

    def test_coding_ai_failure_does_not_grant_correctness(self):
        challenge = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="coding",
            difficulty="easy",
            title="Code",
            description="Write code",
            xp_reward=30,
        )
        response = self.client.post(
            reverse("challenges:submit", args=[challenge.id]),
            data=json.dumps({"code": "print(1)", "time_taken": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_correct"])
        self.assertEqual(response.json()["xp_earned"], 9)


from unittest.mock import patch


class ChallengeGenerationBehaviorTests(TestCase):
    @patch("challenges.views.GeminiService", create=True)
    def test_dashboard_does_not_call_ai(self, gemini):
        user = User.objects.create_user(
            username="challenge-dashboard-user",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("challenges:dashboard"))
        self.assertEqual(response.status_code, 200)
        gemini.assert_not_called()

    def test_dashboard_hides_private_leaderboard_profiles(self):
        viewer = User.objects.create_user(
            username="challenge-viewer",
            password="StrongPass123!",
        )
        private_user = User.objects.create_user(
            username="private-challenge-user",
            password="StrongPass123!",
        )
        private_user.profile.is_public = False
        private_user.profile.save(update_fields=["is_public"])
        ChallengeStreak.objects.create(
            user=private_user,
            total_challenges_completed=999,
        )
        self.client.force_login(viewer)
        response = self.client.get(reverse("challenges:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, private_user.username)

    @override_settings(
        AI_FEATURES_ENABLED=True,
        CODING_CHALLENGES_ENABLED=True,
        RATE_LIMIT_ENABLED=False,
    )
    @patch("challenges.views.GeminiService")
    def test_coding_success_is_feedback_not_verified(self, service_class):
        user = User.objects.create_user(
            username="feedback-challenge-user",
            password="StrongPass123!",
        )
        challenge = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="coding",
            difficulty="easy",
            title="Feedback code",
            description="Write code",
            xp_reward=30,
        )
        service_class.return_value.review_code.return_value = {
            "success": True,
            "feedback_html": "<p>Looks useful</p>",
        }
        self.client.force_login(user)
        response = self.client.post(
            reverse("challenges:submit", args=[challenge.id]),
            data=json.dumps({"code": "print(1)", "time_taken": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_correct"])
        self.assertEqual(response.json()["evaluation_type"], "ai_feedback")
        self.assertIn("Looks useful", response.json()["ai_feedback"])


from datetime import date, timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import CommandError, call_command

from .services import (
    ChallengeGenerationReport,
    generate_challenges_for_date,
    validate_generated_challenge,
)


class ChallengeGenerationServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.target_date = timezone.localdate() + timedelta(days=3)

    def tearDown(self):
        cache.clear()

    @patch("challenges.services.GeminiService")
    def test_valid_provider_payloads_are_normalized_and_saved(self, service_class):
        def generate(**kwargs):
            if kwargs["challenge_type"] == "coding":
                return {
                    "success": True,
                    "data": {
                        "title": "  Write a loop  ",
                        "description": "Print the values.",
                        "starter_code": "for value in values:\n    pass",
                        "example_input": "1 2",
                        "example_output": "1 2",
                        "hints": [" Use iteration "],
                        "difficulty": "hard",
                    },
                }
            return {
                "success": True,
                "data": {
                    "title": "Choose a type",
                    "description": "Which is immutable?",
                    "options": [
                        {"text": "List"},
                        {"text": "Tuple"},
                        {"text": "Dict"},
                        {"text": "Set"},
                    ],
                    "correct_option": 1,
                    "explanation": "A tuple is immutable.",
                    "difficulty": "easy",
                },
            }

        service_class.return_value.generate_daily_challenge.side_effect = generate
        report = generate_challenges_for_date(
            target_date=self.target_date,
            difficulty="medium",
        )

        self.assertEqual(len(report.generated), 2)
        self.assertEqual(report.failed, [])
        coding = Challenge.objects.get(
            date=self.target_date,
            challenge_type="coding",
        )
        theory = Challenge.objects.get(
            date=self.target_date,
            challenge_type="theory",
        )
        self.assertEqual(coding.title, "Write a loop")
        self.assertEqual(coding.hints, ["Use iteration"])
        self.assertEqual(coding.difficulty, "medium")
        self.assertEqual(theory.correct_option, 1)
        self.assertEqual(theory.options[1], {"text": "Tuple"})

    @patch("challenges.services.GeminiService")
    def test_existing_challenges_skip_provider_calls(self, service_class):
        for challenge_type in ("coding", "theory"):
            Challenge.objects.create(
                date=self.target_date,
                challenge_type=challenge_type,
                difficulty="medium",
                title=f"Existing {challenge_type}",
                description="Already generated",
            )

        report = generate_challenges_for_date(self.target_date)

        self.assertCountEqual(report.existing, ["coding", "theory"])
        self.assertEqual(report.generated, [])
        service_class.assert_not_called()

    @patch("challenges.services.GeminiService")
    def test_invalid_theory_payload_is_rejected(self, service_class):
        service_class.return_value.generate_daily_challenge.side_effect = [
            {"success": False, "error": "provider unavailable"},
            {
                "success": True,
                "data": {
                    "title": "Invalid",
                    "description": "Duplicate options",
                    "options": [
                        {"text": "Same"},
                        {"text": "same"},
                        {"text": "C"},
                        {"text": "D"},
                    ],
                    "correct_option": 9,
                    "explanation": "Invalid",
                },
            },
        ]
        with self.assertLogs("challenges.services", level="WARNING"):
            report = generate_challenges_for_date(self.target_date)

        self.assertCountEqual(report.failed, ["coding", "theory"])
        self.assertFalse(Challenge.objects.filter(date=self.target_date).exists())

    @patch(
        "challenges.services.GeminiService",
        side_effect=RuntimeError("SECRET_PROVIDER_INIT"),
    )
    def test_service_initialization_failure_is_reported_without_records(
        self,
        service_class,
    ):
        with self.assertLogs("challenges.services", level="ERROR"):
            report = generate_challenges_for_date(self.target_date)
        self.assertCountEqual(report.failed, ["coding", "theory"])
        self.assertFalse(Challenge.objects.filter(date=self.target_date).exists())

    @patch("challenges.services.GeminiService")
    @patch("challenges.services.cache.add", return_value=False)
    def test_concurrent_generation_returns_locked_report(
        self,
        cache_add,
        service_class,
    ):
        report = generate_challenges_for_date(self.target_date)
        self.assertTrue(report.already_running)
        service_class.assert_not_called()

    def test_validator_rejects_out_of_range_answers(self):
        with self.assertRaisesRegex(ValueError, "correct_option"):
            validate_generated_challenge(
                {
                    "title": "Question",
                    "description": "Choose",
                    "options": [
                        {"text": "A"},
                        {"text": "B"},
                        {"text": "C"},
                        {"text": "D"},
                    ],
                    "correct_option": 4,
                    "explanation": "No",
                },
                "theory",
                "medium",
            )


class ChallengeGenerationCommandTests(TestCase):
    @patch(
        "challenges.management.commands.generate_daily_challenges."
        "generate_challenges_for_date"
    )
    def test_command_reports_success(self, generate):
        generate.return_value = ChallengeGenerationReport(
            generated=[object(), object()],
            existing=["coding"],
        )
        output = StringIO()
        call_command(
            "generate_daily_challenges",
            target_date="2026-08-08",
            difficulty="hard",
            stdout=output,
            no_color=True,
        )
        self.assertIn("Generated 2 challenge(s); 1 already existed", output.getvalue())
        generate.assert_called_once_with(
            target_date=date(2026, 8, 8),
            difficulty="hard",
        )

    @patch(
        "challenges.management.commands.generate_daily_challenges."
        "generate_challenges_for_date"
    )
    def test_command_fails_when_generation_failed(self, generate):
        generate.return_value = ChallengeGenerationReport(failed=["theory"])
        with self.assertRaises(CommandError):
            call_command(
                "generate_daily_challenges",
                stdout=StringIO(),
                no_color=True,
            )

    def test_command_rejects_invalid_date(self):
        with self.assertRaisesRegex(CommandError, "YYYY-MM-DD"):
            call_command(
                "generate_daily_challenges",
                target_date="08/08/2026",
                stdout=StringIO(),
                no_color=True,
            )

    @patch(
        "challenges.management.commands.generate_daily_challenges."
        "generate_challenges_for_date"
    )
    def test_command_treats_active_lock_as_safe_noop(self, generate):
        generate.return_value = ChallengeGenerationReport(already_running=True)
        output = StringIO()
        call_command(
            "generate_daily_challenges",
            stdout=output,
            no_color=True,
        )
        self.assertIn("already running", output.getvalue())


@override_settings(
    AI_FEATURES_ENABLED=False,
    CODING_CHALLENGES_ENABLED=False,
)
class ChallengeSubmissionValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="challenge-validation-user",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)
        self.theory = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="theory",
            difficulty="medium",
            title="Validated theory",
            description="Choose B",
            options=[
                {"text": "A"},
                {"text": "B"},
                {"text": "C"},
                {"text": "D"},
            ],
            correct_option=1,
            xp_reward=15,
        )

    def test_malformed_json_is_rejected_without_attempt(self):
        response = self.client.post(
            reverse("challenges:submit", args=[self.theory.id]),
            data="{",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_JSON")
        self.assertFalse(UserChallenge.objects.exists())

    def test_out_of_range_option_is_rejected_without_attempt(self):
        response = self.client.post(
            reverse("challenges:submit", args=[self.theory.id]),
            data=json.dumps({"selected_option": 99, "time_taken": 4}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserChallenge.objects.exists())

    @patch(
        "challenges.views.BadgeManager.add_xp",
        side_effect=RuntimeError("SECRET_LEDGER_FAILURE"),
    )
    def test_core_reward_failure_rolls_back_and_hides_details(self, add_xp):
        with self.assertLogs("challenges.views", level="ERROR"):
            response = self.client.post(
                reverse("challenges:submit", args=[self.theory.id]),
                data=json.dumps({"selected_option": 1, "time_taken": 4}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("SECRET_LEDGER_FAILURE", response.content.decode())
        self.assertFalse(UserChallenge.objects.exists())
        self.assertFalse(ChallengeStreak.objects.exists())

    def test_two_completed_challenges_increment_total_but_not_daily_streak(self):
        second = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="coding",
            difficulty="medium",
            title="Second challenge",
            description="Write code",
            xp_reward=30,
        )
        first_response = self.client.post(
            reverse("challenges:submit", args=[self.theory.id]),
            data=json.dumps({"selected_option": 1, "time_taken": 4}),
            content_type="application/json",
        )
        second_response = self.client.post(
            reverse("challenges:submit", args=[second.id]),
            data=json.dumps({"code": "print(1)", "time_taken": 4}),
            content_type="application/json",
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        streak = ChallengeStreak.objects.get(user=self.user)
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.total_challenges_completed, 2)


from django.tasks.base import TaskResultStatus

from .tasks import generate_daily_challenges_task


class ChallengeTaskContractTests(TestCase):
    @patch("challenges.tasks.generate_challenges_for_date")
    def test_immediate_backend_executes_json_safe_task(self, generate):
        generated = SimpleNamespace(id=41)
        generate.return_value = ChallengeGenerationReport(
            generated=[generated],
            existing=["theory"],
        )
        result = generate_daily_challenges_task.enqueue(
            target_date="2026-08-21",
            difficulty="hard",
        )
        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        self.assertEqual(
            result.return_value,
            {
                "generated_ids": [41],
                "existing": ["theory"],
                "already_running": False,
            },
        )
        generate.assert_called_once_with(
            target_date=date(2026, 8, 21),
            difficulty="hard",
        )

    @patch("challenges.tasks.generate_challenges_for_date")
    def test_task_failure_is_visible_to_backend(self, generate):
        generate.return_value = ChallengeGenerationReport(failed=["coding"])
        result = generate_daily_challenges_task.enqueue(
            target_date="2026-08-21"
        )
        self.assertEqual(result.status, TaskResultStatus.FAILED)
        self.assertTrue(result.errors)

    @patch("challenges.tasks.generate_challenges_for_date")
    def test_enqueue_command_reports_task_identifier(self, generate):
        generate.return_value = ChallengeGenerationReport(existing=["coding"])
        output = StringIO()
        call_command(
            "enqueue_daily_challenges",
            target_date="2026-08-21",
            stdout=output,
            no_color=True,
        )
        self.assertIn("accepted with status successful", output.getvalue())

    def test_enqueue_command_rejects_invalid_date(self):
        with self.assertRaisesRegex(CommandError, "YYYY-MM-DD"):
            call_command(
                "enqueue_daily_challenges",
                target_date="21/08/2026",
                stdout=StringIO(),
                no_color=True,
            )
