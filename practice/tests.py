import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    AI_FEATURES_ENABLED=True,
    RATE_LIMIT_ENABLED=False,
)
class PracticeAPIValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="practice-api-user",
            password="StrongPass123!",
        )

        self.client.force_login(self.user)

        self.review_url = reverse(
            "practice:check_code"
        )

        self.problem_url = reverse(
            "practice:generate_problem"
        )

    def post(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_invalid_language_is_rejected(self):
        response = self.post(
            self.review_url,
            {
                "code": "print(1)",
                "language": "shell",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json()["error_code"],
            "VALIDATION_ERROR",
        )

    @override_settings(
        AI_CODE_MAX_CHARS=10
    )
    def test_oversized_code_is_rejected(self):
        response = self.post(
            self.review_url,
            {
                "code": "x" * 11,
                "language": "python",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

    def test_invalid_difficulty_is_rejected(self):
        response = self.post(
            self.problem_url,
            {
                "topic": "arrays",
                "difficulty": "impossible",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

    @patch(
        "practice.views.GeminiService",
        side_effect=RuntimeError(
            "SECRET_PRACTICE_PROVIDER"
        ),
    )
    def test_provider_exception_is_hidden(
        self,
        service,
    ):
        with self.assertLogs(
            "practice.views",
            level="ERROR",
        ):
            response = self.post(
                self.review_url,
                {
                    "code": "print(1)",
                    "language": "python",
                },
            )

        self.assertEqual(
            response.status_code,
            500,
        )

        self.assertNotIn(
            "SECRET_PRACTICE_PROVIDER",
            response.content.decode(),
        )

    @patch("practice.views.GeminiService")
    def test_generated_problem_is_parsed_and_normalized(self, service_class):
        service_class.return_value.generate_practice_problem.return_value = {
            "success": True,
            "content": (
                "```json\n"
                '{"title":" Arrays ","description":" Solve it ",'
                '"hints":[" First hint "],"difficulty":"hard"}'
                "\n```"
            ),
        }
        response = self.post(
            self.problem_url,
            {"topic": "arrays", "difficulty": "easy"},
        )
        self.assertEqual(response.status_code, 200)
        problem = response.json()["problem"]
        self.assertEqual(problem["title"], "Arrays")
        self.assertEqual(problem["hints"], ["First hint"])
        self.assertEqual(problem["difficulty"], "easy")

    @patch("practice.views.GeminiService")
    def test_generated_problem_missing_required_fields_is_rejected(
        self,
        service_class,
    ):
        service_class.return_value.generate_practice_problem.return_value = {
            "success": True,
            "content": '{"description":"No title"}',
        }
        response = self.post(
            self.problem_url,
            {"topic": "arrays", "difficulty": "easy"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error_code"], "AI_INVALID_RESPONSE")

    @patch(
        "practice.views.BadgeManager.add_xp",
        side_effect=RuntimeError("SECRET_REVIEW_REWARD_FAILURE"),
    )
    @patch("practice.views.GeminiService")
    def test_reward_failure_rolls_back_review_and_hides_details(
        self,
        service_class,
        add_xp,
    ):
        service_class.return_value.review_code.return_value = {
            "success": True,
            "feedback_html": "<p>Feedback</p>",
        }
        with self.assertLogs("practice.views", level="ERROR"):
            response = self.post(
                self.review_url,
                {"code": "print(1)", "language": "python"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("SECRET_REVIEW_REWARD_FAILURE", response.content.decode())
        self.assertFalse(CodeReview.objects.filter(user=self.user).exists())


from progress.models import UserLevel, XPTransaction
from .models import CodeReview


class CodeReviewRewardIntegrityTests(TestCase):
    @override_settings(AI_FEATURES_ENABLED=True, RATE_LIMIT_ENABLED=False)
    @patch("practice.views.GeminiService")
    def test_same_code_review_is_rewarded_once(self, service_class):
        user = User.objects.create_user(username="review-xp-user", password="StrongPass123!")
        self.client.force_login(user)
        service_class.return_value.review_code.return_value = {
            "success": True,
            "feedback_html": "<p>Safe feedback</p>",
        }
        payload = json.dumps({"code": "print(1)", "language": "python", "problem": "Print one"})
        url = reverse("practice:check_code")
        first = self.client.post(url, data=payload, content_type="application/json")
        second = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json().get("xp_earned"), 15)
        self.assertEqual(second.json().get("xp_earned"), 0)
        self.assertEqual(CodeReview.objects.filter(user=user).count(), 1)
        self.assertEqual(UserLevel.objects.get(user=user).total_xp_earned, 15)
        self.assertEqual(XPTransaction.objects.filter(user=user).count(), 1)
