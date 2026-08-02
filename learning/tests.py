from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Day, Roadmap


class LearningAuthorizationTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            username='roadmap-owner',
            password='StrongPass123!',
        )

        other_user = User.objects.create_user(
            username='other-learner',
            password='StrongPass123!',
        )

        self.roadmap = Roadmap.objects.create(
            user=owner,
            topic='ML',
            title='Private roadmap',
            total_days=1,
            daily_hours=1,
        )

        self.day = Day.objects.create(
            roadmap=self.roadmap,
            day_number=1,
            title='Private day',
            estimated_hours=1,
            order=1,
        )

        self.client.force_login(other_user)

    def test_other_user_cannot_view_roadmap(self):
        response = self.client.get(
            reverse(
                'learning:roadmap_detail',
                args=[self.roadmap.id],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_view_day(self):
        response = self.client.get(
            reverse(
                'learning:day_detail',
                args=[
                    self.roadmap.id,
                    self.day.day_number,
                ],
            )
        )

        self.assertEqual(response.status_code, 404)


class StoredAIContentSecurityTests(TestCase):
    def test_day_page_resanitizes_legacy_html(self):
        user = User.objects.create_user(
            username='stored-ai-user',
            password='StrongPass123!',
        )

        roadmap = Roadmap.objects.create(
            user=user,
            topic='ML',
            title='AI safety roadmap',
            total_days=1,
            daily_hours=1,
        )

        day = Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title='Safe lesson',
            estimated_hours=1,
            order=1,
            ai_content=(
                '<p>Lesson</p>'
                '<script>steal()</script>'
            ),
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse(
                'learning:day_detail',
                args=[
                    roadmap.id,
                    day.day_number,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            '<p>Lesson</p>',
            html=True,
        )

        self.assertNotContains(
            response,
            '<script>steal()</script>',
        )

        self.assertNotContains(
            response,
            'steal()',
        )


from unittest.mock import patch
from django.test import override_settings


@override_settings(
    AI_FEATURES_ENABLED=True,
    RATE_LIMIT_ENABLED=False,
)
class DayContentAPIErrorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="day-content-api-user",
            password="StrongPass123!",
        )

        self.roadmap = Roadmap.objects.create(
            user=self.user,
            topic="ML",
            title="API roadmap",
            total_days=1,
            daily_hours=1,
        )

        self.day = Day.objects.create(
            roadmap=self.roadmap,
            day_number=1,
            title="API day",
            estimated_hours=1,
            order=1,
        )

        self.client.force_login(self.user)

        self.url = reverse(
            "learning:generate_content",
            args=[
                self.roadmap.id,
                self.day.day_number,
            ],
        )

    @patch(
        "learning.views.GeminiService"
    )
    def test_provider_failure_is_safe(
        self,
        service_class,
    ):
        service_class.return_value            .generate_theory            .return_value = {
                "success": False,
                "error": (
                    "SECRET_DAY_PROVIDER_DETAIL"
                ),
            }

        with self.assertLogs(
            "learning.views",
            level="WARNING",
        ):
            response = self.client.post(
                self.url
            )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertNotIn(
            "SECRET_DAY_PROVIDER_DETAIL",
            response.content.decode(),
        )

        self.assertEqual(
            response.json()["error_code"],
            "AI_SERVICE_ERROR",
        )

    @patch(
        "learning.views.GeminiService",
        side_effect=RuntimeError(
            "SECRET_DAY_EXCEPTION"
        ),
    )
    def test_unexpected_exception_is_safe(
        self,
        service_class,
    ):
        with self.assertLogs(
            "learning.views",
            level="ERROR",
        ):
            response = self.client.post(
                self.url
            )

        self.assertEqual(
            response.status_code,
            500,
        )

        self.assertNotIn(
            "SECRET_DAY_EXCEPTION",
            response.content.decode(),
        )

        self.assertEqual(
            response.json()["error_code"],
            "INTERNAL_ERROR",
        )


class DayRewardIntegrityTests(TestCase):
    def test_day_reward_and_activity_are_applied_once(self):
        from progress.models import DailyActivity, UserLevel, XPTransaction

        user = User.objects.create_user(username="day-xp-user", password="StrongPass123!")
        roadmap = Roadmap.objects.create(
            user=user,
            topic="ML",
            title="One day roadmap",
            total_days=1,
            daily_hours=1,
        )
        day = Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title="Only day",
            estimated_hours=1,
            order=1,
        )
        self.client.force_login(user)
        url = reverse("learning:mark_complete", args=[roadmap.id, day.day_number])
        first = self.client.post(url)
        second = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["xp_earned"], 20)
        self.assertEqual(second.json()["xp_earned"], 0)
        self.assertTrue(second.json()["already_completed"])
        self.assertEqual(UserLevel.objects.get(user=user).total_xp_earned, 20)
        self.assertEqual(XPTransaction.objects.filter(user=user).count(), 1)
        activity = DailyActivity.objects.get(user=user)
        self.assertEqual(activity.days_completed, 1)
        self.assertEqual(activity.minutes_studied, 60)
        roadmap.refresh_from_db()
        self.assertEqual(roadmap.status, "completed")
