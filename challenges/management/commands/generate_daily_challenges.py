from django.core.management.base import BaseCommand

from challenges.services import generate_challenges_for_date


class Command(BaseCommand):
    help = "Generate missing global challenges for today"

    def handle(self, *args, **options):
        generated = generate_challenges_for_date()
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {len(generated)} challenge(s)."
            )
        )
