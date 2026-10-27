"""Background-task contracts for scheduler-triggered challenge work."""

from __future__ import annotations

from datetime import date

from django.tasks import task

from .services import generate_challenges_for_date


@task(queue_name="ai")
def generate_daily_challenges_task(
    target_date: str | None = None,
    difficulty: str = "medium",
) -> dict[str, object]:
    """Generate one date's missing challenges through a Django task backend."""
    parsed_date = date.fromisoformat(target_date) if target_date else None
    report = generate_challenges_for_date(
        target_date=parsed_date,
        difficulty=difficulty,
    )
    if report.failed:
        failed = ", ".join(sorted(report.failed))
        raise RuntimeError(
            f"Daily challenge generation failed for: {failed}."
        )
    return {
        "generated_ids": [challenge.id for challenge in report.generated],
        "existing": sorted(report.existing),
        "already_running": report.already_running,
    }
