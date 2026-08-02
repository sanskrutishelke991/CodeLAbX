import json
import re

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Test


class AssessmentQuestionExposureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="assessment-security-user",
            password="StrongPass123!",
        )

        self.test = Test.objects.create(
            user=self.user,
            title="Security test",
            topic="Python",
            num_questions=1,
            questions=[
                {
                    "question": "Choose safely",
                    "options": [
                        "Safe option",
                        (
                            '<img src=x '
                            'onerror="steal()">'
                        ),
                    ],
                    "correct": 0,
                    "explanation": (
                        "SECRET_ANSWER_EXPLANATION"
                    ),
                }
            ],
        )

        self.client.force_login(self.user)

    def test_take_page_excludes_answer_key(self):
        response = self.client.get(
            reverse(
                "assessments:take",
                args=[self.test.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        html = response.content.decode()

        match = re.search(
            (
                r'<script '
                r'id="test-questions-data" '
                r'type="application/json">'
                r'(.*?)'
                r'</script>'
            ),
            html,
            re.DOTALL,
        )

        self.assertIsNotNone(match)

        public_questions = json.loads(
            match.group(1)
        )

        self.assertNotIn(
            "correct",
            public_questions[0],
        )

        self.assertNotIn(
            "explanation",
            public_questions[0],
        )

        self.assertNotIn(
            "SECRET_ANSWER_EXPLANATION",
            html,
        )

        self.assertNotIn(
            '<img src=x onerror="steal()">',
            html,
        )


from unittest.mock import patch


@override_settings(
    AI_FEATURES_ENABLED=True,
    ASSESSMENTS_ENABLED=True,
    RATE_LIMIT_ENABLED=False,
)
class AssessmentGenerationValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=(
                "assessment-generation-user"
            ),
            password="StrongPass123!",
        )

        self.client.force_login(self.user)

        self.url = reverse(
            "assessments:generate"
        )

    def post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_invalid_count_is_rejected(self):
        response = self.post(
            {
                "topic": "Python",
                "num_questions": 31,
            }
        )

        self.assertEqual(
            response.status_code,
            400,
        )

    def test_invalid_difficulty_is_rejected(self):
        response = self.post(
            {
                "topic": "Python",
                "difficulty": "expert",
            }
        )

        self.assertEqual(
            response.status_code,
            400,
        )

    @patch(
        "assessments.views.GeminiService"
    )
    def test_generation_hides_answers(
        self,
        service_class,
    ):
        service_class.return_value            .generate_test_questions            .return_value = {
                "success": True,
                "content": json.dumps(
                    [
                        {
                            "question": (
                                "What is Python?"
                            ),
                            "options": [
                                "Language",
                                "Database",
                            ],
                            "correct": 0,
                            "explanation": (
                                "Python is a language."
                            ),
                        }
                    ]
                ),
            }

        response = self.post(
            {
                "topic": "Python",
                "difficulty": "easy",
                "num_questions": 1,
                "time_limit": 5,
            }
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payload = response.json()

        self.assertNotIn(
            "questions",
            payload,
        )

        self.assertIn(
            "test_id",
            payload,
        )

        created_test = Test.objects.get(
            id=payload["test_id"]
        )

        self.assertEqual(
            created_test.num_questions,
            1,
        )

    @patch(
        "assessments.views.GeminiService"
    )
    def test_invalid_ai_schema_is_rejected(
        self,
        service_class,
    ):
        service_class.return_value            .generate_test_questions            .return_value = {
                "success": True,
                "content": json.dumps(
                    [
                        {
                            "question": "Broken",
                            "options": [],
                            "correct": 99,
                        }
                    ]
                ),
            }

        response = self.post(
            {
                "topic": "Python"
            }
        )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertEqual(
            response.json()["error_code"],
            "AI_INVALID_RESPONSE",
        )

        self.assertEqual(
            Test.objects.filter(
                user=self.user
            ).count(),
            0,
        )
