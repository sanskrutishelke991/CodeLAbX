"""Background-task contracts for rebuildable intelligence snapshots."""

from django.contrib.auth import get_user_model
from django.tasks import task

from intelligence.services.mastery import rebuild_user_skill_states


@task(queue_name="maintenance")
def rebuild_user_skill_states_task(user_id: int) -> dict[str, int]:
    user = get_user_model().objects.get(pk=user_id)
    states = rebuild_user_skill_states(user)
    return {"user_id": user.id, "states_rebuilt": len(states)}
