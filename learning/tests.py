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


class RoadmapLifecycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="lifecycle-owner",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="lifecycle-other",
            password="StrongPass123!",
        )
        self.roadmap = Roadmap.objects.create(
            user=self.owner,
            topic="ML",
            title="Lifecycle roadmap",
            total_days=1,
            daily_hours=1,
        )

    def action(self, action):
        return reverse(
            "learning:roadmap_action",
            args=[self.roadmap.id, action],
        )

    def test_actions_require_post(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.action("pause")).status_code, 405)

    def test_owner_can_pause_resume_and_archive(self):
        self.client.force_login(self.owner)
        self.client.post(self.action("pause"))
        self.roadmap.refresh_from_db()
        self.assertEqual(self.roadmap.status, "paused")
        self.client.post(self.action("resume"))
        self.roadmap.refresh_from_db()
        self.assertEqual(self.roadmap.status, "active")
        self.client.post(self.action("archive"))
        self.roadmap.refresh_from_db()
        self.assertEqual(self.roadmap.status, "archived")

    def test_other_user_cannot_change_roadmap(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.action("delete")).status_code, 404)
        self.assertTrue(Roadmap.objects.filter(id=self.roadmap.id).exists())

    def test_owner_can_delete_roadmap(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.action("delete"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Roadmap.objects.filter(id=self.roadmap.id).exists())


from datetime import date
from decimal import Decimal

from .services import RoadmapGenerator


class RoadmapGeneratorServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="roadmap-service-user",
            password="StrongPass123!",
        )

    def test_generation_creates_exact_days_and_inclusive_end_date(self):
        roadmap = RoadmapGenerator.generate_roadmap(
            user=self.user,
            topic="ML",
            duration_months=1,
            daily_hours=Decimal("1.5"),
            level="beginner",
            start_date=date(2026, 8, 1),
        )
        days = list(roadmap.days.order_by("order"))

        self.assertEqual(roadmap.total_days, 30)
        self.assertEqual(roadmap.end_date, date(2026, 8, 30))
        self.assertEqual(len(days), 30)
        self.assertEqual(days[0].day_number, 1)
        self.assertEqual(days[-1].day_number, 30)
        self.assertEqual(days[-1].order, 30)
        self.assertTrue(all(day.estimated_hours == Decimal("1.5") for day in days))

    def test_invalid_inputs_create_no_partial_roadmap(self):
        invalid_cases = [
            {"topic": "UNKNOWN"},
            {"duration_months": 0},
            {"duration_months": True},
            {"daily_hours": "not-a-number"},
            {"daily_hours": 9},
            {"level": "expert"},
            {"start_date": "2026-08-01"},
        ]
        defaults = {
            "topic": "DSA",
            "duration_months": 1,
            "daily_hours": 1,
            "level": "intermediate",
            "start_date": None,
        }
        for changes in invalid_cases:
            values = {**defaults, **changes}
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    RoadmapGenerator.generate_roadmap(
                        user=self.user,
                        **values,
                    )
        self.assertFalse(Roadmap.objects.filter(user=self.user).exists())

    @patch("learning.services.Day.objects.bulk_create")
    def test_day_write_failure_rolls_back_roadmap(self, bulk_create):
        bulk_create.side_effect = RuntimeError("day write failed")
        with self.assertRaises(RuntimeError):
            RoadmapGenerator.generate_roadmap(
                user=self.user,
                topic="ML",
                duration_months=1,
                daily_hours=1,
            )
        self.assertFalse(Roadmap.objects.filter(user=self.user).exists())

    def test_helper_outputs_cover_module_positions(self):
        self.assertEqual(
            RoadmapGenerator._generate_day_title("Arrays", 1, 1),
            "Arrays",
        )
        self.assertIn(
            "Introduction",
            RoadmapGenerator._generate_day_title("Arrays", 1, 3),
        )
        self.assertIn(
            "Part 2",
            RoadmapGenerator._generate_day_title("Arrays", 2, 4),
        )
        self.assertIn(
            "Practice & Review",
            RoadmapGenerator._generate_day_title("Arrays", 3, 3),
        )
        self.assertEqual(
            RoadmapGenerator.estimate_completion_date(
                date(2026, 1, 1),
                1,
            ),
            date(2026, 1, 30),
        )
        self.assertIsNone(
            RoadmapGenerator.estimate_completion_date(None, 1)
        )


class RoadmapCreationFailureTests(TestCase):
    @patch(
        "learning.views.BadgeManager.add_xp",
        side_effect=RuntimeError("SECRET_ROADMAP_REWARD_FAILURE"),
    )
    def test_reward_failure_rolls_back_and_shows_generic_message(self, add_xp):
        user = User.objects.create_user(
            username="roadmap-rollback-user",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        with self.assertLogs("learning.views", level="ERROR"):
            response = self.client.post(
                reverse("learning:roadmap_create"),
                {
                    "topic": "ML",
                    "duration_months": 1,
                    "daily_hours": "1.0",
                    "level": "beginner",
                    "description": "Should roll back",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Roadmap.objects.filter(user=user).exists())
        self.assertContains(response, "No changes were saved")
        self.assertNotContains(response, "SECRET_ROADMAP_REWARD_FAILURE")
