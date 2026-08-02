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
