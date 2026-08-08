"""Validated, scheduler-safe generation of global daily challenges."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import date

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ai_tools.services import GeminiService

from .models import Challenge

logger = logging.getLogger(__name__)

_CHALLENGE_TYPES = ("coding", "theory")
_DIFFICULTIES = {"easy", "medium", "hard"}


class GeneratedChallengeError(ValueError):
    """The provider returned a structurally invalid challenge."""


@dataclass
class ChallengeGenerationReport:
    generated: list[Challenge] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    already_running: bool = False


def _required_text(data: dict, key: str, maximum: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GeneratedChallengeError(f"{key} must be non-empty text.")
    value = value.strip()
    if len(value) > maximum:
        raise GeneratedChallengeError(f"{key} is too long.")
    return value


def _optional_text(data: dict, key: str, maximum: int) -> str:
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > maximum:
        raise GeneratedChallengeError(f"{key} must be bounded text.")
    return value.strip()


def _validate_coding(data: dict, difficulty: str) -> dict:
    hints = data.get("hints", [])
    if not isinstance(hints, list) or len(hints) > 5:
        raise GeneratedChallengeError("hints must be a list of at most five items.")
    normalized_hints = []
    for hint in hints:
        if not isinstance(hint, str) or not hint.strip() or len(hint) > 500:
            raise GeneratedChallengeError("each hint must be bounded text.")
        normalized_hints.append(hint.strip())

    return {
        "title": _required_text(data, "title", 300),
        "description": _required_text(data, "description", 5000),
        "difficulty": difficulty,
        "xp_reward": 30,
        "starter_code": _optional_text(data, "starter_code", 20_000),
        "example_input": _optional_text(data, "example_input", 5000),
        "example_output": _optional_text(data, "example_output", 5000),
        "hints": normalized_hints,
    }


def _validate_theory(data: dict, difficulty: str) -> dict:
    options = data.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise GeneratedChallengeError("theory options must contain four items.")

    normalized_options = []
    seen = set()
    for option in options:
        if not isinstance(option, dict):
            raise GeneratedChallengeError("each theory option must be an object.")
        text = _required_text(option, "text", 500)
        normalized = text.casefold()
        if normalized in seen:
            raise GeneratedChallengeError("theory options must be unique.")
        seen.add(normalized)
        normalized_options.append({"text": text})

    correct = data.get("correct_option")
    if (
        isinstance(correct, bool)
        or not isinstance(correct, int)
        or not 0 <= correct < len(normalized_options)
    ):
        raise GeneratedChallengeError("correct_option is outside the option range.")

    return {
        "title": _required_text(data, "title", 300),
        "description": _required_text(data, "description", 5000),
        "difficulty": difficulty,
        "xp_reward": 15,
        "options": normalized_options,
        "correct_option": correct,
        "explanation": _required_text(data, "explanation", 5000),
    }


def validate_generated_challenge(
    data: object,
    challenge_type: str,
    difficulty: str,
) -> dict:
    """Normalize one provider payload before it reaches a JSONField."""
    if challenge_type not in _CHALLENGE_TYPES:
        raise ValueError("challenge_type must be coding or theory.")
    if difficulty not in _DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium, or hard.")
    if not isinstance(data, dict):
        raise GeneratedChallengeError("challenge payload must be an object.")
    if challenge_type == "coding":
        return _validate_coding(data, difficulty)
    return _validate_theory(data, difficulty)


def generate_challenges_for_date(
    target_date: date | None = None,
    difficulty: str = "medium",
) -> ChallengeGenerationReport:
    """Generate only missing challenge types under a cache-backed lock."""
    target_date = target_date or timezone.localdate()
    if not isinstance(target_date, date):
        raise ValueError("target_date must be a date.")
    if difficulty not in _DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium, or hard.")

    report = ChallengeGenerationReport()
    lock_key = f"challenge-generation:{target_date.isoformat()}"
    lock_token = secrets.token_urlsafe(18)
    if not cache.add(lock_key, lock_token, timeout=5 * 60):
        report.already_running = True
        return report

    try:
        missing = []
        for challenge_type in _CHALLENGE_TYPES:
            exists = Challenge.objects.filter(
                date=target_date,
                challenge_type=challenge_type,
            ).exists()
            if exists:
                report.existing.append(challenge_type)
            else:
                missing.append(challenge_type)

        if not missing:
            return report

        try:
            service = GeminiService()
        except Exception:
            logger.exception("Daily challenge service initialization failed")
            report.failed.extend(missing)
            return report

        for challenge_type in missing:
            result = service.generate_daily_challenge(
                challenge_type=challenge_type,
                difficulty=difficulty,
            )
            if not result.get("success"):
                logger.warning(
                    "Daily %s challenge provider call failed: %s",
                    challenge_type,
                    result.get("error", "unknown provider failure"),
                )
                report.failed.append(challenge_type)
                continue

            try:
                values = validate_generated_challenge(
                    result.get("data"),
                    challenge_type,
                    difficulty,
                )
            except GeneratedChallengeError as exc:
                logger.warning(
                    "Daily %s challenge payload was rejected: %s",
                    challenge_type,
                    exc,
                )
                report.failed.append(challenge_type)
                continue

            with transaction.atomic():
                challenge, created = Challenge.objects.get_or_create(
                    date=target_date,
                    challenge_type=challenge_type,
                    defaults=values,
                )
            if created:
                report.generated.append(challenge)
            else:
                report.existing.append(challenge_type)

        return report
    finally:
        try:
            if cache.get(lock_key) == lock_token:
                cache.delete(lock_key)
        except Exception:
            logger.exception("Daily challenge lock cleanup failed")
