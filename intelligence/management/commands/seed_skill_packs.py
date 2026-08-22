from django.core.management.base import BaseCommand

from intelligence.services.skill_packs import seed_skill_packs


class Command(BaseCommand):
    help = "Validate and idempotently seed versioned Learning Intelligence packs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check_only",
            help="Validate files without writing database records.",
        )

    def handle(self, *args, **options):
        summary = seed_skill_packs(check_only=options["check_only"])
        action = "Validated" if options["check_only"] else "Seeded"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {summary['packs']} packs, {summary['skills']} skills, "
                f"{summary['memberships']} memberships, and "
                f"{summary['prerequisites']} prerequisites."
            )
        )
