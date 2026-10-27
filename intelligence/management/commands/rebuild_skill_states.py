from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from intelligence.models import LearningEvent
from intelligence.services.mastery import rebuild_user_skill_states
from intelligence.tasks import rebuild_user_skill_states_task


class Command(BaseCommand):
    help = "Rebuild deterministic SkillState snapshots from immutable events."

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--user", type=int, dest="user_id")
        target.add_argument("--all", action="store_true", dest="all_users")
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Use the configured Django task backend.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        if options["user_id"]:
            user_ids = [options["user_id"]]
        else:
            user_ids = list(
                LearningEvent.objects.order_by()
                .values_list("user_id", flat=True)
                .distinct()
            )

        rebuilt = 0
        for user_id in user_ids:
            try:
                user = user_model.objects.get(pk=user_id)
            except user_model.DoesNotExist as exc:
                raise CommandError(f"User {user_id} does not exist.") from exc
            if options["enqueue"]:
                result = rebuild_user_skill_states_task.enqueue(user_id=user.id)
                status = getattr(result.status, "value", str(result.status)).lower()
                if status == "failed":
                    raise CommandError(
                        f"Skill-state rebuild task failed for user {user.id}."
                    )
                self.stdout.write(
                    f"Task {result.id} accepted for user {user.id} ({status})."
                )
            else:
                rebuilt += len(rebuild_user_skill_states(user))

        if not options["enqueue"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Rebuilt {rebuilt} skill-state snapshot(s) for "
                    f"{len(user_ids)} user(s)."
                )
            )
