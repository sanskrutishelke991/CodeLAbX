"""Send or enqueue opted-in weekly learning report emails."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from accounts.services.weekly_reports import send_due_weekly_reports
from accounts.tasks import send_weekly_reports_task


class Command(BaseCommand):
    help = (
        "Process opted-in weekly learning reports. An external scheduler must "
        "invoke this command; CodeLabX does not schedule itself."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            help="Send date in YYYY-MM-DD format; defaults to the local date.",
        )
        parser.add_argument("--user", dest="user_id", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--enqueue", action="store_true")

    def handle(self, *args, **options):
        target_date_text = options["target_date"]
        target_date = None
        if target_date_text:
            try:
                target_date = date.fromisoformat(target_date_text)
            except ValueError as exc:
                raise CommandError("--date must use YYYY-MM-DD format.") from exc
        if options["force"] and options["user_id"] is None:
            raise CommandError("--force requires --user to prevent bulk off-day sends.")

        if options["enqueue"]:
            result = send_weekly_reports_task.enqueue(
                target_date=target_date_text,
                user_id=options["user_id"],
                dry_run=options["dry_run"],
                force=options["force"],
            )
            status = getattr(result.status, "value", str(result.status)).lower()
            self.stdout.write(
                f"Task {result.id} accepted with status {status}."
            )
            if status == "failed":
                raise CommandError(
                    "The immediate task execution failed; inspect server logs."
                )
            return

        report = send_due_weekly_reports(
            target_date=target_date,
            user_id=options["user_id"],
            dry_run=options["dry_run"],
            force=options["force"],
        )
        self.stdout.write(
            "Weekly reports: "
            f"eligible={report.eligible} sent={report.sent} "
            f"already_sent={report.already_sent} "
            f"in_progress={report.in_progress} failed={report.failed} "
            f"dry_run={str(report.dry_run).lower()}."
        )
        if report.failed:
            raise CommandError(
                f"{report.failed} weekly report delivery attempt(s) failed."
            )
