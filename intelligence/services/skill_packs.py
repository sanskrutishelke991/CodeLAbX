"""Load, validate, and idempotently seed versioned Skill Pack JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from intelligence.models import (
    Skill,
    SkillPack,
    SkillPackMembership,
    SkillPrerequisite,
)

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,119}$")
DEFAULT_PACK_DIRECTORY = Path(__file__).resolve().parent.parent / "skill_packs"


@dataclass(frozen=True)
class ValidatedSkillPacks:
    packs: list[dict]
    skills: dict[str, dict]
    memberships: list[dict]
    prerequisites: list[dict]


def _required_text(data, key, maximum):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{key} must be non-empty text.")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{key} exceeds {maximum} characters.")
    return value


def _ratio(value, field):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric.") from exc
    if not Decimal("0") <= parsed <= Decimal("1"):
        raise ValidationError(f"{field} must be between 0 and 1.")
    return parsed


def _load_payloads(directory: Path) -> list[dict]:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise ValidationError("No Skill Pack files were found.")
    payloads = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"Invalid Skill Pack file: {path.name}.") from exc
        if not isinstance(payload, dict):
            raise ValidationError(f"Skill Pack {path.name} must contain an object.")
        payload["_source"] = path.name
        payloads.append(payload)
    return payloads


def validate_skill_pack_directory(
    directory: Path | str = DEFAULT_PACK_DIRECTORY,
) -> ValidatedSkillPacks:
    directory = Path(directory)
    payloads = _load_payloads(directory)
    packs = []
    skills = {}
    raw_memberships = []
    raw_prerequisites = []
    seen_pack_versions = set()

    for payload in payloads:
        source = payload["_source"]
        code = _required_text(payload, "code", 80)
        if not CODE_PATTERN.fullmatch(code):
            raise ValidationError(f"Invalid pack code in {source}.")
        version = payload.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValidationError(f"Invalid pack version in {source}.")
        pack_key = (code, version)
        if pack_key in seen_pack_versions:
            raise ValidationError(f"Duplicate pack/version: {code} v{version}.")
        seen_pack_versions.add(pack_key)
        packs.append(
            {
                "code": code,
                "name": _required_text(payload, "name", 160),
                "description": _required_text(payload, "description", 5000),
                "version": version,
                "source": source,
            }
        )

        definitions = payload.get("skills", [])
        memberships = payload.get("memberships", [])
        prerequisites = payload.get("prerequisites", [])
        if not all(isinstance(value, list) for value in (definitions, memberships, prerequisites)):
            raise ValidationError(f"Skill Pack arrays are invalid in {source}.")

        for item in definitions:
            if not isinstance(item, dict):
                raise ValidationError(f"Skill definitions must be objects in {source}.")
            skill_code = _required_text(item, "code", 120)
            if not CODE_PATTERN.fullmatch(skill_code):
                raise ValidationError(f"Invalid skill code {skill_code!r} in {source}.")
            difficulty = item.get("difficulty_band", 1)
            half_life = item.get("half_life_days", 60)
            if isinstance(difficulty, bool) or not isinstance(difficulty, int) or not 1 <= difficulty <= 5:
                raise ValidationError(f"Invalid difficulty for {skill_code}.")
            if isinstance(half_life, bool) or not isinstance(half_life, int) or not 1 <= half_life <= 3650:
                raise ValidationError(f"Invalid half-life for {skill_code}.")
            definition = {
                "code": skill_code,
                "name": _required_text(item, "name", 160),
                "description": _required_text(item, "description", 5000),
                "domain": _required_text(item, "domain", 60),
                "difficulty_band": difficulty,
                "default_half_life_days": half_life,
            }
            previous = skills.get(skill_code)
            if previous and previous != definition:
                raise ValidationError(
                    f"Conflicting definitions for shared skill {skill_code}."
                )
            skills[skill_code] = definition

        for item in memberships:
            if not isinstance(item, dict):
                raise ValidationError(f"Memberships must be objects in {source}.")
            raw_memberships.append(
                {
                    "pack_code": code,
                    "pack_version": version,
                    "source": source,
                    **item,
                }
            )
        for item in prerequisites:
            if not isinstance(item, dict):
                raise ValidationError(f"Prerequisites must be objects in {source}.")
            raw_prerequisites.append({"source": source, **item})

    memberships = []
    membership_keys = set()
    membership_orders = set()
    for item in raw_memberships:
        skill_code = _required_text(item, "skill", 120)
        if skill_code not in skills:
            raise ValidationError(f"Unknown membership skill {skill_code}.")
        order = item.get("order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ValidationError(f"Invalid membership order for {skill_code}.")
        pack_key = (item["pack_code"], item["pack_version"])
        membership_key = (*pack_key, skill_code)
        order_key = (*pack_key, order)
        if membership_key in membership_keys or order_key in membership_orders:
            raise ValidationError(f"Duplicate membership/order in {item['source']}.")
        membership_keys.add(membership_key)
        membership_orders.add(order_key)
        memberships.append(
            {
                "pack_code": item["pack_code"],
                "pack_version": item["pack_version"],
                "skill_code": skill_code,
                "order": order,
                "is_core": bool(item.get("core", False)),
                "is_required": bool(item.get("required", True)),
            }
        )

    prerequisites = []
    edge_keys = set()
    graph = {code: set() for code in skills}
    for item in raw_prerequisites:
        skill_code = _required_text(item, "skill", 120)
        required_code = _required_text(item, "requires", 120)
        if skill_code not in skills or required_code not in skills:
            raise ValidationError(
                f"Unknown prerequisite edge {required_code} -> {skill_code}."
            )
        if skill_code == required_code:
            raise ValidationError(f"Skill {skill_code} cannot require itself.")
        key = (required_code, skill_code)
        if key in edge_keys:
            raise ValidationError(f"Duplicate prerequisite edge {key}.")
        edge_keys.add(key)
        graph[required_code].add(skill_code)
        prerequisites.append(
            {
                "prerequisite_code": required_code,
                "dependent_code": skill_code,
                "minimum_mastery": _ratio(
                    item.get("minimum_mastery", "0.6000"),
                    "minimum_mastery",
                ),
                "minimum_confidence": _ratio(
                    item.get("minimum_confidence", "0.4000"),
                    "minimum_confidence",
                ),
                "strength": _ratio(item.get("strength", "1.0000"), "strength"),
            }
        )

    visiting = set()
    visited = set()

    def visit(code):
        if code in visiting:
            raise ValidationError(f"Prerequisite cycle detected at {code}.")
        if code in visited:
            return
        visiting.add(code)
        for dependent in graph[code]:
            visit(dependent)
        visiting.remove(code)
        visited.add(code)

    for code in graph:
        visit(code)

    return ValidatedSkillPacks(
        packs=packs,
        skills=skills,
        memberships=memberships,
        prerequisites=prerequisites,
    )


@transaction.atomic
def seed_skill_packs(
    directory: Path | str = DEFAULT_PACK_DIRECTORY,
    *,
    check_only=False,
) -> dict[str, int]:
    validated = validate_skill_pack_directory(directory)
    summary = {
        "packs": len(validated.packs),
        "skills": len(validated.skills),
        "memberships": len(validated.memberships),
        "prerequisites": len(validated.prerequisites),
    }
    if check_only:
        return summary

    skill_objects = {}
    for code, definition in validated.skills.items():
        skill, _ = Skill.objects.update_or_create(
            code=code,
            defaults={**definition, "is_active": True},
        )
        skill_objects[code] = skill

    pack_objects = {}
    for definition in validated.packs:
        SkillPack.objects.filter(code=definition["code"]).exclude(
            version=definition["version"]
        ).update(is_active=False)
        pack, _ = SkillPack.objects.update_or_create(
            code=definition["code"],
            version=definition["version"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "is_active": True,
            },
        )
        pack_objects[(definition["code"], definition["version"])] = pack

    membership_ids_by_pack = {key: [] for key in pack_objects}
    for definition in validated.memberships:
        pack_key = (definition["pack_code"], definition["pack_version"])
        membership, _ = SkillPackMembership.objects.update_or_create(
            pack=pack_objects[pack_key],
            skill=skill_objects[definition["skill_code"]],
            defaults={
                "order": definition["order"],
                "is_core": definition["is_core"],
                "is_required": definition["is_required"],
            },
        )
        membership_ids_by_pack[pack_key].append(membership.id)
    for pack_key, membership_ids in membership_ids_by_pack.items():
        SkillPackMembership.objects.filter(pack=pack_objects[pack_key]).exclude(
            id__in=membership_ids
        ).delete()

    SkillPrerequisite.objects.all().delete()
    SkillPrerequisite.objects.bulk_create(
        [
            SkillPrerequisite(
                prerequisite=skill_objects[item["prerequisite_code"]],
                dependent=skill_objects[item["dependent_code"]],
                minimum_mastery=item["minimum_mastery"],
                minimum_confidence=item["minimum_confidence"],
                strength=item["strength"],
            )
            for item in validated.prerequisites
        ]
    )
    return summary
