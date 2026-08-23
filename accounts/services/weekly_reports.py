"""Deterministic weekly learning reports and idempotent email delivery."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.template.loader import render_to_string
from django.utils import timezone

from assessments.models import Test
from challenges.models import UserChallenge
from intelligence.models import (
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
)
from intelligence.services.passport import build_skill_passport
from intelligence.services.retention import analyze_retention
from learning.models import Day
from progress.models import DailyActivity

from accounts.models import EmailPreference, WeeklyReportDelivery

logger = logging.getLogger(__name__)
PENDING_RETRY_AFTER = timedelta(minutes=30)


@dataclass(frozen=True)
class WeeklyReportData:
    period_start: date
    period_end: date
    active_days: int
    study_minutes: int
    completed_days: int
    roadmaps_touched: int
    completed_tests: int
    average_test_score: float | None
    completed_challenges: int
    evidence_records: int
    scoreable_evidence_records: int
    evidenced_skills: int
    passport_observed_skills: int | None
    passport_total_skills: int | None
    retention_due_skills: int | None
    current_mission_title: str | None
    current_mission_status: str | None

    @property
    def study_hours(self):
        return round(self.study_minutes / 60, 1)

    @property
    def has_recorded_activity(self):
        return any(
            (
                self.study_minutes,
                self.completed_days,
                self.completed_tests,
                self.completed_challenges,
                self.evidence_records,
            )
        )


@dataclass(frozen=True)
class RenderedWeeklyReport:
    data: WeeklyReportData
    subject: str
    text_body: str
    html_body: str
    content_hash: str


@dataclass(frozen=True)
class WeeklyReportBatchResult:
    target_date: date
    eligible: int
    sent: int
    already_sent: int
    in_progress: int
    failed: int
    dry_run: bool


def _valid_account_email(user):
    email = (user.email or "").strip().lower()
    validate_email(email)
    return email


def build_weekly_report(user, preference=None, *, period_end=None):
    """Build one report from authoritative rows without AI-generated claims."""
    preference = preference or EmailPreference(user=user)
    period_end = period_end or timezone.localdate()
    period_start = period_end - timedelta(days=6)

    activity = {"study_minutes": 0, "active_days": 0}
    completed_day_count = 0
    roadmaps_touched = 0
    test_summary = {"count": 0, "average": None}
    completed_challenges = 0
    if preference.include_activity:
        activity = DailyActivity.objects.filter(
            user=user,
            date__range=(period_start, period_end),
        ).aggregate(
            study_minutes=Sum("minutes_studied"),
            active_days=Count(
                "id",
                filter=Q(minutes_studied__gt=0) | Q(days_completed__gt=0),
            ),
        )
        completed_days = Day.objects.filter(
            roadmap__user=user,
            is_completed=True,
            completed_at__date__range=(period_start, period_end),
        )
        completed_day_count = completed_days.count()
        roadmaps_touched = completed_days.values("roadmap_id").distinct().count()
        test_summary = Test.objects.filter(
            user=user,
            status="completed",
            completed_at__date__range=(period_start, period_end),
        ).aggregate(
            count=Count("id"),
            average=Avg("score"),
        )
        completed_challenges = UserChallenge.objects.filter(
            user=user,
            status="completed",
            completed_at__date__range=(period_start, period_end),
        ).count()

    event_summary = {"total": 0, "scoreable": 0, "skills": 0}
    if preference.include_skill_progress:
        event_summary = LearningEvent.objects.filter(
            user=user,
            occurred_at__date__range=(period_start, period_end),
        ).aggregate(
            total=Count("id"),
            scoreable=Count("id", filter=Q(outcome__isnull=False)),
            skills=Count("skill_id", distinct=True),
        )

    passport_observed = None
    passport_total = None
    retention_due = None
    profile = None
    if preference.include_skill_progress or preference.include_next_steps:
        profile = (
            LearnerIntelligenceProfile.objects.filter(user=user)
            .select_related("selected_pack")
            .first()
        )
    if profile and profile.diagnostics_complete:
        if preference.include_skill_progress:
            passport = build_skill_passport(user, profile)
            passport_observed = passport.observed_skill_count
            passport_total = len(passport.skills)
        if preference.include_next_steps:
            retention_due = len(analyze_retention(user, profile).candidates)

    current_mission = None
    if preference.include_next_steps:
        current_mission = (
            Mission.objects.filter(
                user=user,
                status__in={"proposed", "accepted", "active", "postponed"},
            )
            .order_by("-created_at")
            .first()
        )

    average = test_summary["average"]
    return WeeklyReportData(
        period_start=period_start,
        period_end=period_end,
        active_days=activity["active_days"] or 0,
        study_minutes=activity["study_minutes"] or 0,
        completed_days=completed_day_count,
        roadmaps_touched=roadmaps_touched,
        completed_tests=test_summary["count"] or 0,
        average_test_score=(round(float(average), 1) if average is not None else None),
        completed_challenges=completed_challenges,
        evidence_records=event_summary["total"] or 0,
        scoreable_evidence_records=event_summary["scoreable"] or 0,
        evidenced_skills=event_summary["skills"] or 0,
        passport_observed_skills=passport_observed,
        passport_total_skills=passport_total,
        retention_due_skills=retention_due,
        current_mission_title=current_mission.title if current_mission else None,
        current_mission_status=(
            current_mission.get_status_display() if current_mission else None
        ),
    )


def render_weekly_report(user, preference=None, *, period_end=None):
    preference = preference or EmailPreference(user=user)
    data = build_weekly_report(
        user,
        preference,
        period_end=period_end,
    )
    subject = (
        "Your CodeLabX weekly learning report — "
        f"{data.period_start:%d %b} to {data.period_end:%d %b %Y}"
    )
    context = {
        "report_user": user,
        "preference": preference,
        "report": data,
    }
    text_body = render_to_string("emails/weekly_report.txt", context).strip() + "\n"
    html_body = render_to_string("emails/weekly_report.html", context).strip()
    content_hash = hashlib.sha256(
        (subject + "\n" + text_body + "\n" + html_body).encode("utf-8")
    ).hexdigest()
    return RenderedWeeklyReport(
        data=data,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        content_hash=content_hash,
    )


def _send_rendered_report(user, rendered):
    recipient = _valid_account_email(user)
    message = EmailMultiAlternatives(
        subject=rendered.subject,
        body=rendered.text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        headers={"X-Auto-Response-Suppress": "All"},
    )
    message.attach_alternative(rendered.html_body, "text/html")
    delivered = message.send(fail_silently=False)
    if delivered != 1:
        raise RuntimeError("The configured email backend did not accept the report.")
    return delivered


def send_weekly_report_preview(user, preference=None, *, period_end=None):
    """Send an explicit user-requested preview without changing weekly ledger state."""
    rendered = render_weekly_report(
        user,
        preference,
        period_end=period_end,
    )
    _send_rendered_report(user, rendered)
    return rendered


def send_scheduled_weekly_report(user, preference, *, period_end):
    """Send one idempotent scheduled report and record only delivery metadata."""
    rendered = render_weekly_report(
        user,
        preference,
        period_end=period_end,
    )
    now = timezone.now()
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        delivery = (
            WeeklyReportDelivery.objects.select_for_update()
            .filter(
                user=user,
                period_start=rendered.data.period_start,
                period_end=rendered.data.period_end,
            )
            .first()
        )
        if delivery and delivery.status == "sent":
            return "already_sent", delivery
        overlapping_sent = (
            WeeklyReportDelivery.objects.filter(
                user=user,
                status="sent",
                period_start__lte=rendered.data.period_end,
                period_end__gte=rendered.data.period_start,
            )
            .exclude(id=delivery.id if delivery else None)
            .order_by("-period_end")
            .first()
        )
        if overlapping_sent is not None:
            return "already_sent", overlapping_sent
        if (
            delivery
            and delivery.status == "pending"
            and delivery.last_attempt_at
            and delivery.last_attempt_at > now - PENDING_RETRY_AFTER
        ):
            return "in_progress", delivery
        if delivery is None:
            delivery = WeeklyReportDelivery(
                user=user,
                period_start=rendered.data.period_start,
                period_end=rendered.data.period_end,
            )
        delivery.status = "pending"
        delivery.subject = rendered.subject
        delivery.content_hash = rendered.content_hash
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.sent_at = None
        delivery.error_code = ""
        delivery.save()

    try:
        _send_rendered_report(user, rendered)
    except Exception:
        logger.exception(
            "Weekly report delivery failed",
            extra={"user_id": user.id, "delivery_id": delivery.id},
        )
        with transaction.atomic():
            failed = WeeklyReportDelivery.objects.select_for_update().get(
                id=delivery.id
            )
            failed.status = "failed"
            failed.sent_at = None
            failed.error_code = "email_backend_error"
            failed.save()
        return "failed", failed

    with transaction.atomic():
        sent = WeeklyReportDelivery.objects.select_for_update().get(id=delivery.id)
        sent.status = "sent"
        sent.sent_at = timezone.now()
        sent.error_code = ""
        sent.save()
    return "sent", sent


def send_due_weekly_reports(
    *,
    target_date=None,
    user_id=None,
    dry_run=False,
    force=False,
):
    """Process opted-in recipients; an external scheduler must invoke this daily."""
    target_date = target_date or timezone.localdate()
    preferences = (
        EmailPreference.objects.filter(
            weekly_report_enabled=True,
            user__is_active=True,
        )
        .exclude(user__email="")
        .select_related("user")
        .order_by("user_id")
    )
    if user_id is not None:
        preferences = preferences.filter(user_id=user_id)
    if not force:
        preferences = preferences.filter(report_weekday=target_date.weekday())
    preference_list = list(preferences)
    if dry_run:
        return WeeklyReportBatchResult(
            target_date=target_date,
            eligible=len(preference_list),
            sent=0,
            already_sent=0,
            in_progress=0,
            failed=0,
            dry_run=True,
        )

    counts = {
        "sent": 0,
        "already_sent": 0,
        "in_progress": 0,
        "failed": 0,
    }
    period_end = target_date - timedelta(days=1)
    for preference in preference_list:
        try:
            status, _delivery = send_scheduled_weekly_report(
                preference.user,
                preference,
                period_end=period_end,
            )
        except (ValidationError, ValueError):
            logger.warning(
                "Weekly report recipient was skipped because account email is invalid",
                extra={"user_id": preference.user_id},
            )
            counts["failed"] += 1
        else:
            counts[status] += 1
    return WeeklyReportBatchResult(
        target_date=target_date,
        eligible=len(preference_list),
        sent=counts["sent"],
        already_sent=counts["already_sent"],
        in_progress=counts["in_progress"],
        failed=counts["failed"],
        dry_run=False,
    )
