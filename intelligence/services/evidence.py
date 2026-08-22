"""Validated idempotent writes to the learning-evidence ledger."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from intelligence.models import LearningEvent, Skill
from intelligence.services.mastery import rebuild_skill_state

MAX_METADATA_BYTES = 4096


def _decimal(value, field, *, nullable=False):
    if nullable and value is None:
        return None
    if isinstance(value, bool):
        raise ValidationError({field: "Boolean values are not accepted."})
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "A numeric value is required."}) from exc
    return parsed


@transaction.atomic
def record_learning_event(
    *,
    user,
    skill_code: str,
    event_type: str,
    source_type: str,
    source_id: str,
    idempotency_key: str,
    outcome=None,
    difficulty=Decimal("0.5000"),
    evidence_weight=Decimal("1.000"),
    hints_used=0,
    retry_count=0,
    duration_seconds=0,
    metadata=None,
    occurred_at=None,
    recalculate=True,
):
    """Create one immutable event and optionally rebuild its skill state."""
    if not skill_code or len(skill_code) > 120:
        raise ValidationError({"skill_code": "A valid skill code is required."})
    if not source_type or len(source_type) > 50:
        raise ValidationError({"source_type": "A valid source type is required."})
    source_id = str(source_id).strip()
    if not source_id or len(source_id) > 100:
        raise ValidationError({"source_id": "A valid source ID is required."})
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValidationError(
            {"idempotency_key": "A valid idempotency key is required."}
        )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (hints_used, retry_count, duration_seconds)
    ):
        raise ValidationError("Count and duration values must be non-negative integers.")

    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValidationError({"metadata": "Metadata must be an object."})
    encoded_metadata = json.dumps(
        metadata,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded_metadata) > MAX_METADATA_BYTES:
        raise ValidationError({"metadata": "Metadata exceeds the 4 KB limit."})

    skill = Skill.objects.get(code=skill_code, is_active=True)
    defaults = {
        "skill": skill,
        "event_type": event_type,
        "source_type": source_type,
        "source_id": source_id,
        "outcome": _decimal(outcome, "outcome", nullable=True),
        "difficulty": _decimal(difficulty, "difficulty"),
        "evidence_weight": _decimal(evidence_weight, "evidence_weight"),
        "hints_used": hints_used,
        "retry_count": retry_count,
        "duration_seconds": duration_seconds,
        "metadata": metadata,
        "occurred_at": occurred_at or timezone.now(),
    }
    event, created = LearningEvent.objects.get_or_create(
        user=user,
        idempotency_key=idempotency_key,
        defaults=defaults,
    )
    if not created and (
        event.skill_id != skill.id
        or event.event_type != event_type
        or event.source_type != source_type
        or event.source_id != source_id
    ):
        raise ValidationError(
            "The idempotency key is already attached to a different event."
        )

    state = rebuild_skill_state(user, skill) if recalculate else None
    return event, created, state
