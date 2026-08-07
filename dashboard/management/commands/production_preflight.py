"""Report provider-neutral blockers before a production deployment."""

from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from codelabx.readiness import collect_production_findings


class Command(BaseCommand):
    help = "Validate production settings without printing secrets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit machine-readable findings.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as blockers.",
        )

    def handle(self, *args, **options):
        findings = collect_production_findings(settings)
        errors = [item for item in findings if item.severity == "error"]
        warnings = [item for item in findings if item.severity == "warning"]

        if options["as_json"]:
            self.stdout.write(
                json.dumps(
                    {
                        "ready": not errors and not (
                            options["strict"] and warnings
                        ),
                        "errors": len(errors),
                        "warnings": len(warnings),
                        "findings": [item.as_dict() for item in findings],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            for item in findings:
                line = f"{item.severity.upper()} {item.code}: {item.message}"
                style = (
                    self.style.ERROR
                    if item.severity == "error"
                    else self.style.WARNING
                )
                self.stdout.write(style(line))
            self.stdout.write(
                f"Preflight summary: {len(errors)} error(s), "
                f"{len(warnings)} warning(s)."
            )

        if errors or (options["strict"] and warnings):
            raise CommandError("Production preflight found deployment blockers.")

        if not options["as_json"]:
            self.stdout.write(self.style.SUCCESS("Production preflight passed."))
