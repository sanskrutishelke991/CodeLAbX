import json
import re

from django.contrib.auth.models import User
from django.test import TestCase
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
