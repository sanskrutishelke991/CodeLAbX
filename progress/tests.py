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
from .services import ActivityLogger, AnalyticsService
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

class AnalyticsExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="analytics-export-user",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other-analytics-user",
            password="StrongPass123!",
        )
        DailyActivity.objects.create(
            user=self.user,
            date=timezone.localdate(),
            minutes_studied=37,
        )
        DailyActivity.objects.create(
            user=self.other_user,
            date=timezone.localdate(),
            minutes_studied=999,
        )

    def test_export_requires_authentication(self):
        response = self.client.get(reverse("progress:analytics_export"))
        self.assertEqual(response.status_code, 302)

    def test_export_is_private_download_with_recorded_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("progress:analytics_export"))
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("Recorded study hours,0.6", body)
        self.assertIn(",37", body)
        self.assertNotIn("999", body)


from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from learning.models import Day, Roadmap


class ProgressServiceHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="progress-service-user",
            password="StrongPass123!",
        )

    def test_activity_totals_and_windows_are_bounded(self):
        today = timezone.localdate()
        DailyActivity.objects.create(
            user=self.user,
            date=today,
            minutes_studied=75,
            days_completed=1,
        )
        DailyActivity.objects.create(
            user=self.user,
            date=today - timedelta(days=1),
            minutes_studied=45,
            days_completed=1,
        )
        stats = AnalyticsService.get_learning_stats(self.user)
        user_stats = AnalyticsService.get_study_consistency(self.user, days=2)

        self.assertEqual(stats["total_minutes"], 120)
        self.assertEqual(stats["total_hours"], 2.0)
        self.assertEqual(user_stats, 100.0)
        self.assertEqual(len(AnalyticsService.get_weekly_activity(self.user)["labels"]), 28)
        with self.assertRaises(ValueError):
            AnalyticsService.get_study_consistency(self.user, days=0)
        with self.assertRaises(ValueError):
            ActivityLogger.get_heatmap_data(self.user, days=4000)

    def test_test_statistics_use_percentages_and_skip_unfinished_rows(self):
        Test.objects.create(
            user=self.user,
            title="Full marks",
            topic="Python",
            status="completed",
            score=50,
            total_marks=50,
            completed_at=timezone.now() - timedelta(days=1),
        )
        Test.objects.create(
            user=self.user,
            title="Half marks",
            topic="Python",
            status="completed",
            score=50,
            total_marks=100,
            completed_at=timezone.now(),
        )
        Test.objects.create(
            user=self.user,
            title="Missing completion time",
            topic="Python",
            status="completed",
            score=100,
            total_marks=100,
            completed_at=None,
        )

        performance = AnalyticsService.get_test_performance(self.user)
        stats = AnalyticsService.get_learning_stats(self.user)

        self.assertEqual(performance["data"], [100.0, 50.0])
        self.assertEqual(stats["total_tests"], 2)
        self.assertEqual(stats["avg_test_score"], 75.0)
        self.assertNotIn("estimated_days_to_finish", stats)

    def test_topic_distribution_uses_annotated_completed_days(self):
        roadmap = Roadmap.objects.create(
            user=self.user,
            topic="ML",
            title="Distribution roadmap",
            total_days=2,
            daily_hours=2,
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title="Done",
            estimated_hours=2,
            order=1,
            is_completed=True,
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=2,
            title="Pending",
            estimated_hours=2,
            order=2,
        )
        result = AnalyticsService.get_topic_distribution(self.user)
        self.assertEqual(result["labels"], ["Machine Learning"])
        self.assertEqual(result["data"], [2.0])


class AchievementPageQueryTests(TestCase):
    def test_earned_badges_render_without_per_badge_queries(self):
        user = User.objects.create_user(
            username="achievement-query-user",
            password="StrongPass123!",
        )
        badges = []
        for index in range(20):
            badges.append(
                Badge.objects.create(
                    name=f"Query badge {index}",
                    description="Query test",
                    icon="Q",
                    category="learning",
                    rarity="common",
                    xp_reward=1,
                    requirement_type="topics_completed",
                    requirement_value=index + 1,
                )
            )
        from .models import UserBadge

        UserBadge.objects.create(user=user, badge=badges[0])
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("progress:achievements"))

        self.assertEqual(response.status_code, 200)
        earned_entry = response.context["categorized"]["learning"][0]
        self.assertTrue(earned_entry["is_earned"])
        self.assertIsNotNone(earned_entry["earned_at"])
        self.assertLessEqual(
            len(queries),
            14,
            msg=f"Achievement page exceeded query budget: {len(queries)}",
        )


class SeedBadgesCommandTests(TestCase):
    def test_seed_badges_is_idempotent_and_repairs_values(self):
        output = StringIO()
        call_command("seed_badges", stdout=output, no_color=True)
        first_count = Badge.objects.count()
        badge = Badge.objects.get(name="First Steps")
        badge.description = "Drifted description"
        badge.save(update_fields=["description"])

        second_output = StringIO()
        call_command("seed_badges", stdout=second_output, no_color=True)
        badge.refresh_from_db()

        self.assertGreater(first_count, 0)
        self.assertEqual(Badge.objects.count(), first_count)
        self.assertNotEqual(badge.description, "Drifted description")
        self.assertIn("updated", second_output.getvalue().lower())
