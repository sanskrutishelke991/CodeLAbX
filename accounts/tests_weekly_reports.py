from __future__ import annotations

import io
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assessments.models import Test
from challenges.models import Challenge, UserChallenge
from intelligence.models import (
    LearnerIntelligenceProfile,
    Mission,
    Skill,
    SkillPack,
)
from intelligence.services.evidence import record_learning_event
from intelligence.services.skill_packs import seed_skill_packs
from learning.models import Day, Roadmap
from progress.models import DailyActivity

from .forms import EmailPreferenceForm
from .models import EmailPreference, WeeklyReportDelivery
from .services.weekly_reports import (
    build_weekly_report,
    render_weekly_report,
    send_due_weekly_reports,
    send_scheduled_weekly_report,
    send_weekly_report_preview,
)
from .tasks import send_weekly_reports_task


class WeeklyReportFixtureMixin:
    def create_report_data(self):
        self.period_end = timezone.localdate()
        self.period_start = self.period_end - timedelta(days=6)
        DailyActivity.objects.create(
            user=self.user,
            date=self.period_end,
            minutes_studied=90,
            days_completed=1,
        )
        roadmap = Roadmap.objects.create(
            user=self.user,
            topic="DSA",
            title="Weekly report roadmap",
            total_days=1,
            daily_hours=1,
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title="Completed report day",
            estimated_hours=1,
            order=1,
            is_completed=True,
            completed_at=timezone.now(),
        )
        Test.objects.create(
            user=self.user,
            title="Weekly report assessment",
            topic="Debugging",
            status="completed",
            score=80,
            total_marks=100,
            completed_at=timezone.now(),
        )
        challenge = Challenge.objects.create(
            date=self.period_end,
            challenge_type="theory",
            difficulty="medium",
            title="Weekly report challenge",
            description="A deterministic question",
            options=[{"text": "A"}, {"text": "B"}],
            correct_option=0,
        )
        UserChallenge.objects.create(
            user=self.user,
            challenge=challenge,
            status="completed",
            selected_option=0,
            is_correct=True,
            completed_at=timezone.now(),
        )
        skill = Skill.objects.get(code="programming.debugging")
        record_learning_event(
            user=self.user,
            skill_code=skill.code,
            event_type="assessment_answer",
            source_type="weekly_report_test",
            source_id="1",
            idempotency_key="weekly-report-evidence-1",
            outcome=Decimal("1.0000"),
        )
        Mission.objects.create(
            user=self.user,
            primary_skill=skill,
            mission_type="practice",
            status="proposed",
            title="Weekly report mission",
            description="A truthful next step.",
            rationale={"reason": "test"},
            success_criteria={"rule": "test"},
            expected_minutes=20,
            recommendation_key="w" * 64,
        )


class WeeklyReportServiceTests(WeeklyReportFixtureMixin, TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="weekly-service-user",
            email="weekly-service@example.com",
            password="StrongPass123!",
        )
        pack = SkillPack.objects.get(code="programming_dsa", version=1)
        LearnerIntelligenceProfile.objects.create(
            user=self.user,
            primary_goal="placement",
            selected_pack=pack,
            routing_diagnostic_completed_at=timezone.now(),
            goal_diagnostic_completed_at=timezone.now(),
        )
        self.preference = EmailPreference.objects.create(
            user=self.user,
            weekly_report_enabled=True,
            report_weekday=timezone.localdate().weekday(),
        )
        self.create_report_data()

    def test_report_uses_authoritative_recorded_values(self):
        report = build_weekly_report(
            self.user,
            self.preference,
            period_end=self.period_end,
        )
        self.assertEqual(report.active_days, 1)
        self.assertEqual(report.study_minutes, 90)
        self.assertEqual(report.study_hours, 1.5)
        self.assertEqual(report.completed_days, 1)
        self.assertEqual(report.roadmaps_touched, 1)
        self.assertEqual(report.completed_tests, 1)
        self.assertEqual(report.average_test_score, 80.0)
        self.assertEqual(report.completed_challenges, 1)
        self.assertEqual(report.evidence_records, 1)
        self.assertEqual(report.scoreable_evidence_records, 1)
        self.assertEqual(report.evidenced_skills, 1)
        self.assertEqual(report.passport_observed_skills, 1)
        self.assertGreater(report.passport_total_skills, 1)
        self.assertEqual(report.retention_due_skills, 0)
        self.assertEqual(report.current_mission_title, "Weekly report mission")

    def test_disabled_sections_are_not_queried_or_rendered_as_progress(self):
        preference = EmailPreference(
            user=self.user,
            include_activity=False,
            include_skill_progress=False,
            include_next_steps=True,
        )
        rendered = render_weekly_report(
            self.user,
            preference,
            period_end=self.period_end,
        )
        self.assertEqual(rendered.data.study_minutes, 0)
        self.assertEqual(rendered.data.evidence_records, 0)
        self.assertNotIn("RECORDED ACTIVITY", rendered.text_body)
        self.assertNotIn("EVIDENCE AND SKILL PROGRESS", rendered.text_body)
        self.assertIn("NEXT STEPS", rendered.text_body)

    def test_rendering_is_deterministic_and_makes_no_ai_claim(self):
        first = render_weekly_report(
            self.user,
            self.preference,
            period_end=self.period_end,
        )
        second = render_weekly_report(
            self.user,
            self.preference,
            period_end=self.period_end,
        )
        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(len(first.content_hash), 64)
        self.assertIn("recorded CodeLabX activity only", first.text_body)
        self.assertIn("not independently verified", first.text_body)
        source = (
            Path(__file__).resolve().parent
            / "services"
            / "weekly_reports.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Gemini", source)
        self.assertNotIn("google.genai", source)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_explicit_preview_sends_multipart_without_scheduled_ledger(self):
        rendered = send_weekly_report_preview(
            self.user,
            self.preference,
            period_end=self.period_end,
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.user.email])
        self.assertEqual(message.subject, rendered.subject)
        self.assertEqual(len(message.alternatives), 1)
        self.assertFalse(WeeklyReportDelivery.objects.exists())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_scheduled_delivery_is_idempotent_and_metadata_only(self):
        first_status, first = send_scheduled_weekly_report(
            self.user,
            self.preference,
            period_end=self.period_end,
        )
        second_status, second = send_scheduled_weekly_report(
            self.user,
            self.preference,
            period_end=self.period_end,
        )
        self.assertEqual(first_status, "sent")
        self.assertEqual(second_status, "already_sent")
        self.assertEqual(first.id, second.id)
        overlap_status, overlap = send_scheduled_weekly_report(
            self.user,
            self.preference,
            period_end=self.period_end + timedelta(days=3),
        )
        self.assertEqual(overlap_status, "already_sent")
        self.assertEqual(overlap.id, first.id)
        self.assertEqual(len(mail.outbox), 1)
        first.refresh_from_db()
        self.assertEqual(first.status, "sent")
        self.assertEqual(first.attempt_count, 1)
        self.assertEqual(len(first.content_hash), 64)
        self.assertFalse(hasattr(first, "body"))

    @patch(
        "accounts.services.weekly_reports._send_rendered_report",
        side_effect=RuntimeError("SECRET_PROVIDER_FAILURE"),
    )
    def test_backend_failure_records_generic_retryable_state(self, sender):
        with self.assertLogs(
            "accounts.services.weekly_reports",
            level="ERROR",
        ):
            status, delivery = send_scheduled_weekly_report(
                self.user,
                self.preference,
                period_end=self.period_end,
            )
        self.assertEqual(status, "failed")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "failed")
        self.assertEqual(delivery.error_code, "email_backend_error")
        self.assertNotIn("SECRET_PROVIDER_FAILURE", delivery.error_code)
        self.assertEqual(delivery.attempt_count, 1)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_due_batch_respects_opt_in_weekday_and_dry_run(self):
        target_date = self.period_end
        self.preference.report_weekday = target_date.weekday()
        self.preference.save()
        other = User.objects.create_user(
            username="weekly-disabled-user",
            email="weekly-disabled@example.com",
            password="StrongPass123!",
        )
        EmailPreference.objects.create(
            user=other,
            weekly_report_enabled=False,
            report_weekday=target_date.weekday(),
        )
        dry = send_due_weekly_reports(
            target_date=target_date,
            dry_run=True,
        )
        self.assertEqual(dry.eligible, 1)
        self.assertTrue(dry.dry_run)
        self.assertFalse(WeeklyReportDelivery.objects.exists())
        sent = send_due_weekly_reports(target_date=target_date)
        self.assertEqual(sent.sent, 1)
        self.assertEqual(sent.eligible, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_task_contract_and_dry_run_command_are_json_safe(self):
        target_date = self.period_end
        self.preference.report_weekday = target_date.weekday()
        self.preference.save()
        result = send_weekly_reports_task.enqueue(
            target_date=target_date.isoformat(),
            dry_run=True,
        )
        self.assertEqual(result.return_value["eligible"], 1)
        self.assertTrue(result.return_value["dry_run"])
        output = io.StringIO()
        call_command(
            "send_weekly_reports",
            target_date=target_date.isoformat(),
            dry_run=True,
            stdout=output,
        )
        self.assertIn("eligible=1", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("send_weekly_reports", force=True)


class EmailPreferenceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="email-model-user",
            email="email-model@example.com",
            password="StrongPass123!",
        )

    def test_opt_in_requires_valid_email_and_one_selected_section(self):
        no_email = User.objects.create_user(
            username="email-no-address",
            password="StrongPass123!",
        )
        with self.assertRaises(ValidationError):
            EmailPreference.objects.create(
                user=no_email,
                weekly_report_enabled=True,
            )
        with self.assertRaises(ValidationError):
            EmailPreference.objects.create(
                user=self.user,
                weekly_report_enabled=True,
                include_activity=False,
                include_skill_progress=False,
                include_next_steps=False,
            )

    def test_form_is_explicit_opt_in_and_saves_sections(self):
        empty = EmailPreferenceForm({"report_weekday": "0"}, user=self.user)
        self.assertTrue(empty.is_valid(), empty.errors)
        preference = empty.save()
        self.assertFalse(preference.weekly_report_enabled)
        enabled = EmailPreferenceForm(
            {
                "weekly_report_enabled": "on",
                "report_weekday": "4",
                "include_activity": "on",
                "include_skill_progress": "on",
            },
            instance=preference,
            user=self.user,
        )
        self.assertTrue(enabled.is_valid(), enabled.errors)
        preference = enabled.save()
        self.assertTrue(preference.weekly_report_enabled)
        self.assertEqual(preference.report_weekday, 4)
        self.assertTrue(preference.include_activity)
        self.assertFalse(preference.include_next_steps)

    def test_delivery_requires_exact_period_and_database_uniqueness(self):
        end = timezone.localdate()
        start = end - timedelta(days=6)
        delivery = WeeklyReportDelivery.objects.create(
            user=self.user,
            period_start=start,
            period_end=end,
            status="pending",
        )
        self.assertEqual(delivery.status, "pending")
        with self.assertRaises(ValidationError):
            WeeklyReportDelivery.objects.create(
                user=self.user,
                period_start=start,
                period_end=end - timedelta(days=1),
            )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WeeklyReportDelivery.objects.bulk_create(
                    [
                        WeeklyReportDelivery(
                            user=self.user,
                            period_start=start,
                            period_end=end,
                        )
                    ]
                )

    def test_email_models_are_registered_in_admin(self):
        self.assertIn(EmailPreference, admin.site._registry)
        self.assertIn(WeeklyReportDelivery, admin.site._registry)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_PREVIEW_ATTEMPTS=10,
    EMAIL_PREVIEW_WINDOW_SECONDS=3600,
)
class EmailPreferenceViewTests(WeeklyReportFixtureMixin, TestCase):
    def setUp(self):
        cache.clear()
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="email-view-user",
            email="email-view@example.com",
            password="StrongPass123!",
        )
        pack = SkillPack.objects.get(code="programming_dsa", version=1)
        LearnerIntelligenceProfile.objects.create(
            user=self.user,
            primary_goal="placement",
            selected_pack=pack,
            routing_diagnostic_completed_at=timezone.now(),
            goal_diagnostic_completed_at=timezone.now(),
        )
        self.create_report_data()
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def test_get_does_not_silently_opt_in_and_post_saves_preference(self):
        url = reverse("accounts:email_preferences")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reports are off until you enable them")
        self.assertFalse(EmailPreference.objects.filter(user=self.user).exists())
        saved = self.client.post(
            url,
            {
                "weekly_report_enabled": "on",
                "report_weekday": str(timezone.localdate().weekday()),
                "include_activity": "on",
                "include_skill_progress": "on",
                "include_next_steps": "on",
            },
        )
        self.assertRedirects(saved, url)
        self.assertTrue(
            EmailPreference.objects.get(user=self.user).weekly_report_enabled
        )

    def test_preview_and_explicit_test_send_are_real_and_post_only(self):
        preview_url = reverse("accounts:weekly_report_preview")
        preview = self.client.get(preview_url)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "90 min")
        self.assertContains(preview, "Weekly report mission")
        send_url = reverse("accounts:send_weekly_report_test")
        self.assertEqual(self.client.get(send_url).status_code, 405)
        sent = self.client.post(send_url, follow=True)
        self.assertEqual(sent.status_code, 200)
        self.assertContains(
            sent,
            "no external inbox delivery is claimed",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(WeeklyReportDelivery.objects.exists())

    def test_settings_link_and_account_export_include_email_controls(self):
        preference = EmailPreference.objects.create(
            user=self.user,
            weekly_report_enabled=True,
            report_weekday=timezone.localdate().weekday(),
        )
        settings_page = self.client.get(reverse("accounts:settings"))
        self.assertContains(settings_page, "Manage email reports")
        self.assertContains(settings_page, preference.get_report_weekday_display())
        response = self.client.post(reverse("accounts:export_account_data"))
        payload = json.loads(response.content)
        self.assertTrue(payload["email_preference"]["weekly_report_enabled"])
        self.assertEqual(payload["weekly_report_deliveries"], [])

    def test_email_pages_require_authentication(self):
        self.client.logout()
        for name in (
            "accounts:email_preferences",
            "accounts:weekly_report_preview",
        ):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response.url)
