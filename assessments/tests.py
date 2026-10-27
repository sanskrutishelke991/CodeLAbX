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


from datetime import timedelta
from django.utils import timezone
from progress.models import XPTransaction
from .models import TestAttempt


class AssessmentAttemptLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="attempt-lifecycle-user",
            password="StrongPass123!",
        )
        self.test = Test.objects.create(
            user=self.user,
            title="Lifecycle test",
            topic="Python",
            num_questions=1,
            time_limit_minutes=10,
            questions=[
                {
                    "question": "Choose A",
                    "options": ["A", "B"],
                    "correct": 0,
                    "explanation": "A is correct",
                }
            ],
        )
        self.client.force_login(self.user)

    def test_take_page_creates_and_reuses_attempt(self):
        url = reverse("assessments:take", args=[self.test.id])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(TestAttempt.objects.filter(test=self.test).count(), 1)
        self.assertIsNotNone(TestAttempt.objects.get(test=self.test).deadline_at)

    def test_submission_finalizes_once_and_awards_once(self):
        self.client.get(reverse("assessments:take", args=[self.test.id]))
        attempt = TestAttempt.objects.get(test=self.test)
        url = reverse("assessments:submit", args=[self.test.id])
        payload = json.dumps({"attempt_id": attempt.id, "answers": {"0": 0}, "time_taken": 1})
        first = self.client.post(url, data=payload, content_type="application/json")
        second = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["score"], 100)
        self.assertGreater(first.json()["xp_earned"], 0)
        self.assertTrue(second.json()["already_finalized"])
        self.assertEqual(second.json()["xp_earned"], 0)
        self.assertEqual(XPTransaction.objects.filter(user=self.user, event_type="assessment-completed").count(), 1)

    def test_expired_attempt_is_finalized_with_zero(self):
        self.client.get(reverse("assessments:take", args=[self.test.id]))
        attempt = TestAttempt.objects.get(test=self.test)
        attempt.deadline_at = timezone.now() - timedelta(minutes=1)
        attempt.save(update_fields=["deadline_at"])
        response = self.client.post(
            reverse("assessments:submit", args=[self.test.id]),
            data=json.dumps({"attempt_id": attempt.id, "answers": {"0": 0}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 410)
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_finalized)
        self.assertEqual(attempt.score, 0)


class AssessmentModelPropertyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="assessment-model-user",
            password="StrongPass123!",
        )
        self.test = Test.objects.create(
            user=self.user,
            title="Property test",
            topic="Python",
            score=None,
            total_marks=100,
        )

    def test_percentage_handles_missing_and_zero_denominator(self):
        self.assertEqual(self.test.percentage, 0)
        self.test.score = 25
        self.test.total_marks = 50
        self.assertEqual(self.test.percentage, 50.0)
        self.test.total_marks = 0
        self.assertEqual(self.test.percentage, 0)

    def test_grade_boundaries_are_deterministic(self):
        boundaries = {
            100: "A+",
            95: "A",
            91: "A-",
            88: "B+",
            84: "B",
            81: "B-",
            78: "C+",
            74: "C",
            71: "C-",
            68: "D+",
            64: "D",
            61: "D-",
            59: "F",
        }
        self.test.total_marks = 100
        for score, grade in boundaries.items():
            with self.subTest(score=score):
                self.test.score = score
                self.assertEqual(self.test.grade, grade)

    def test_attempt_percentage_handles_unscored_attempt(self):
        self.test.total_marks = 80
        self.test.save(update_fields=["total_marks"])
        attempt = TestAttempt.objects.create(
            test=self.test,
            user=self.user,
            score=None,
        )
        self.assertEqual(attempt.percentage, 0)
        attempt.score = 40
        self.assertEqual(attempt.percentage, 50.0)
