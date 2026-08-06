from pathlib import Path
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Badge, UserLevel, XPTransaction
from .services import BadgeManager


class ProgressPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='visible-learner',
            password='StrongPass123!',
        )

        UserLevel.objects.create(
            user=self.user,
            total_xp_earned=250,
        )

        self.client.force_login(self.user)

        self.badge = Badge.objects.create(
            name='Code Route Test',
            description=(
                'Used to verify the badge detail route.'
            ),
            icon='T',
            category='practice',
            rarity='common',
            xp_reward=10,
            requirement_type='code_reviews',
            requirement_value=1,
        )

    def test_locked_code_badge_detail_renders(self):
        response = self.client.get(
            reverse(
                'progress:badge_detail',
                args=[self.badge.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.badge.name)
        self.assertContains(response, '0%')

    def test_missing_badge_returns_404(self):
        response = self.client.get(
            reverse(
                'progress:badge_detail',
                args=[999999],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_leaderboard_displays_public_user(self):
        response = self.client.get(
            reverse('progress:leaderboard')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            self.user.username,
        )

    def test_leaderboard_hides_private_profile(self):
        private_user = User.objects.create_user(
            username='private-learner',
            password='StrongPass123!',
        )

        private_user.profile.is_public = False
        private_user.profile.save(
            update_fields=['is_public']
        )

        UserLevel.objects.create(
            user=private_user,
            total_xp_earned=9999,
        )

        response = self.client.get(
            reverse('progress:leaderboard')
        )

        self.assertNotContains(
            response,
            private_user.username,
        )


class XPTransactionTests(TestCase):
    def test_same_idempotency_key_awards_once(self):
        user = User.objects.create_user(
            username="xp-ledger-user",
            password="StrongPass123!",
        )
        first = BadgeManager.add_xp(
            user,
            20,
            "Test event",
            idempotency_key="test:event:1",
            event_type="test",
        )
        second = BadgeManager.add_xp(
            user,
            20,
            "Test event",
            idempotency_key="test:event:1",
            event_type="test",
        )
        level = UserLevel.objects.get(user=user)
        self.assertEqual(first["xp_added"], 20)
        self.assertEqual(second["xp_added"], 0)
        self.assertTrue(second["duplicate"])
        self.assertEqual(level.total_xp_earned, 20)
        self.assertEqual(XPTransaction.objects.filter(user=user).count(), 1)


from datetime import timedelta
from django.utils import timezone
from .models import DailyActivity
from .services import AnalyticsService
from assessments.models import Test


class AnalyticsCorrectnessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="analytics-user",
            password="StrongPass123!",
        )

    def test_consistency_never_counts_an_extra_day(self):
        today = timezone.localdate()
        for offset in range(31):
            DailyActivity.objects.create(
                user=self.user,
                date=today - timedelta(days=offset),
                minutes_studied=10,
            )
        self.assertEqual(
            AnalyticsService.get_study_consistency(self.user, days=30),
            100.0,
        )

    def test_test_performance_returns_latest_twenty(self):
        for index in range(21):
            test = Test.objects.create(
                user=self.user,
                title=f"Test {index}",
                topic="Python",
                status="completed",
                score=index,
                completed_at=timezone.now() + timedelta(minutes=index),
            )
        result = AnalyticsService.get_test_performance(self.user)
        self.assertEqual(len(result["data"]), 20)
        self.assertEqual(result["data"][0], 1.0)
        self.assertEqual(result["data"][-1], 20.0)

    def test_analytics_template_contains_no_safe_json_filter(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("progress:analytics"))
        self.assertEqual(response.status_code, 200)
        source = (Path(__file__).resolve().parent.parent / "templates" / "progress" / "analytics.html").read_text()
        self.assertNotIn("|safe", source)
        self.assertContains(response, 'id="weekly-activity-labels"')
