"""Background-task contract for weekly learning-report email delivery."""

from __future__ import annotations

from datetime import date

from django.tasks import task

from accounts.services.weekly_reports import send_due_weekly_reports


@task(queue_name="maintenance")
def send_weekly_reports_task(
    target_date: str | None = None,
    user_id: int | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, object]:
    parsed_date = date.fromisoformat(target_date) if target_date else None
    result = send_due_weekly_reports(
        target_date=parsed_date,
        user_id=user_id,
        dry_run=dry_run,
        force=force,
    )
    return {
        "target_date": result.target_date.isoformat(),
        "eligible": result.eligible,
        "sent": result.sent,
        "already_sent": result.already_sent,
        "in_progress": result.in_progress,
        "failed": result.failed,
        "dry_run": result.dry_run,
    }
