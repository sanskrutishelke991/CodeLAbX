"""Scheduled generation of global daily challenges."""

from django.db import transaction
from django.utils import timezone

from ai_tools.services import GeminiService

from .models import Challenge


def generate_challenges_for_date(target_date=None):
    target_date = target_date or timezone.localdate()
    generated = []

    for challenge_type in ["coding", "theory"]:
        if Challenge.objects.filter(
            date=target_date,
            challenge_type=challenge_type,
        ).exists():
            continue

        result = GeminiService().generate_daily_challenge(
            challenge_type=challenge_type,
            difficulty="medium",
        )
        if not result.get("success"):
            continue

        data = result["data"]
        values = {
            "title": str(data.get("title", "Daily Challenge"))[:300],
            "description": str(data.get("description", "")),
            "difficulty": data.get("difficulty", "medium"),
            "xp_reward": 30 if challenge_type == "coding" else 15,
        }
        if challenge_type == "coding":
            values.update(
                {
                    "starter_code": data.get("starter_code", ""),
                    "example_input": data.get("example_input", ""),
                    "example_output": data.get("example_output", ""),
                    "hints": data.get("hints", []),
                }
            )
        else:
            values.update(
                {
                    "options": data.get("options", []),
                    "correct_option": data.get("correct_option", 0),
                    "explanation": data.get("explanation", ""),
                }
            )

        with transaction.atomic():
            challenge, created = Challenge.objects.get_or_create(
                date=target_date,
                challenge_type=challenge_type,
                defaults=values,
            )
        if created:
            generated.append(challenge)

    return generated
