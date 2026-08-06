from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from challenges.models import Challenge


class RouteSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='smoke-user',
            password='StrongPass123!',
        )

    def test_public_pages_render(self):
        routes = [
            'landing',
            'accounts:login',
            'accounts:register',
        ]

        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name)
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_authenticated_pages_render(self):
        self.client.force_login(self.user)

        routes = [
            'dashboard:home',
            'accounts:profile',
            'accounts:profile_edit',
            'accounts:settings',
            'learning:roadmaps',
            'learning:roadmap_create',
            'content:library',
            'content:my_videos',
            'practice:task_list',
            'practice:examiner',
            'assessments:quiz_list',
            'assessments:create',
            'ai_tools:home',
            'ai_tools:image_analyzer',
            'ai_tools:image_history',
            'progress:achievements',
            'progress:leaderboard',
            'progress:analytics',
            'notes:list',
            'notes:create',
            'notes:bookmarks',
        ]

        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name)
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    @patch(
        'challenges.views.'
        'get_or_create_today_challenges'
    )
    def test_challenge_dashboard_without_ai_call(
        self,
        generator,
    ):
        generator.return_value = (
            Challenge.objects.none()
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse('challenges:dashboard')
        )

        self.assertEqual(response.status_code, 200)


from django.contrib import admin
from accounts.models import UserProfile
from assessments.models import Test
from challenges.models import Challenge
from content.models import Video
from learning.models import Roadmap
from notes.models import Note
from practice.models import CodeReview
from progress.models import XPTransaction


class AdminRegistrationTests(TestCase):
    def test_operational_models_are_registered(self):
        for model in [
            UserProfile,
            Test,
            Challenge,
            Video,
            Roadmap,
            Note,
            CodeReview,
            XPTransaction,
        ]:
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)


from django.utils import timezone
from learning.models import Day, Roadmap
from progress.models import DailyActivity, UserBadge, Badge, XPTransaction


class DashboardTruthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="truth-dashboard-user",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

    def test_dashboard_uses_recorded_values(self):
        roadmap = Roadmap.objects.create(
            user=self.user,
            topic="ML",
            title="Truth roadmap",
            total_days=2,
            daily_hours=1,
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title="Completed",
            estimated_hours=1,
            order=1,
            is_completed=True,
            completed_at=timezone.now(),
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=2,
            title="Next",
            estimated_hours=1,
            order=2,
        )
        DailyActivity.objects.create(
            user=self.user,
            date=timezone.localdate(),
            minutes_studied=60,
            days_completed=1,
        )
        badge = Badge.objects.create(
            name="Truth badge",
            description="Actually earned",
            icon="T",
            category="learning",
            rarity="common",
            xp_reward=1,
            requirement_type="topics_completed",
            requirement_value=1,
        )
        UserBadge.objects.create(user=self.user, badge=badge)
        XPTransaction.objects.create(
            user=self.user,
            amount=20,
            event_type="day-completed",
            reason="Completed a real day",
            idempotency_key="truth-event",
        )

        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Truth roadmap")
        self.assertContains(response, "Truth badge")
        self.assertContains(response, "Completed a real day")
        self.assertContains(response, "1 active days")

    def test_dashboard_template_has_no_random_demo_data(self):
        template = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / "dashboard"
            / "home.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Math.random", template)
        self.assertNotIn("127</div>", template)
        self.assertNotIn("Completed Day 5 of ML Roadmap", template)
        self.assertNotIn("Try Neural Networks next", template)
        self.assertNotIn("Lofi Beats to Study", template)

    def test_heatmap_contains_exactly_365_days(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(len(response.context["heatmap_data"]), 365)
