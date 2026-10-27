"""Generate missing global daily challenges for a scheduler."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from challenges.services import generate_challenges_for_date


class Command(BaseCommand):
    help = "Generate validated missing global challenges for one date."

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
        target_date = None
        if options["target_date"]:
            try:
                target_date = date.fromisoformat(options["target_date"])
            except ValueError as exc:
                raise CommandError("--date must use YYYY-MM-DD format.") from exc

        report = generate_challenges_for_date(
            target_date=target_date,
            difficulty=options["difficulty"],
        )
        if report.already_running:
            self.stdout.write(
                self.style.WARNING(
                    "Challenge generation is already running for this date."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {len(report.generated)} challenge(s); "
                f"{len(report.existing)} already existed."
            )
        )
        if report.failed:
            failed = ", ".join(sorted(report.failed))
            raise CommandError(
                f"Generation failed validation or provider access for: {failed}."
            )
