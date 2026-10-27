"""Enqueue daily challenge generation through Django's Tasks contract."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from challenges.tasks import generate_daily_challenges_task


class Command(BaseCommand):
    help = "Enqueue validated daily challenge generation for a scheduler."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            help="Target date in YYYY-MM-DD format; defaults to the local date.",
        )
        parser.add_argument(
            "--difficulty",
            choices=("easy", "medium", "hard"),
            default="medium",
        )

    def handle(self, *args, **options):
        target_date = options["target_date"]
        if target_date:
            try:
                date.fromisoformat(target_date)
            except ValueError as exc:
                raise CommandError("--date must use YYYY-MM-DD format.") from exc

        result = generate_daily_challenges_task.enqueue(
            target_date=target_date,
            difficulty=options["difficulty"],
        )
        status = getattr(result.status, "value", str(result.status)).lower()
        self.stdout.write(
            f"Task {result.id} accepted with status {status}."
        )
        if status == "failed":
            raise CommandError(
                "The immediate task execution failed; inspect server logs."
            )
