"""Validated rule-based roadmap generation."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import Day, Roadmap


class RoadmapGenerator:
    """Create deterministic ML/DSA roadmaps from bounded preferences."""

    TOPIC_TEMPLATES = {
        "ML": {
            "name": "Machine Learning",
            "modules": [
                "Introduction to ML",
                "Python for ML",
                "Linear Algebra Basics",
                "Statistics & Probability",
                "Data Preprocessing",
                "Supervised Learning",
                "Unsupervised Learning",
                "Neural Networks",
                "Deep Learning",
                "Model Evaluation",
                "Feature Engineering",
                "Ensemble Methods",
                "Model Deployment",
                "ML Projects",
                "Advanced Topics",
            ],
        },
        "DSA": {
            "name": "Data Structures & Algorithms",
            "modules": [
                "Introduction to DSA",
                "Time & Space Complexity",
                "Arrays & Strings",
                "Linked Lists",
                "Stacks & Queues",
                "Trees & Binary Trees",
                "Heaps & Priority Queues",
                "Hash Tables",
                "Recursion",
                "Sorting Algorithms",
                "Searching Algorithms",
                "Graphs Basics",
                "Graph Traversal",
                "Dynamic Programming",
                "Greedy Algorithms",
                "Advanced Data Structures",
                "Algorithm Design",
                "DSA Projects",
            ],
        },
    }
    LEVELS = {"beginner", "intermediate", "advanced"}

    @classmethod
    def _validated_inputs(
        cls,
        topic,
        duration_months,
        daily_hours,
        level,
        start_date,
    ):
        if topic not in cls.TOPIC_TEMPLATES:
            raise ValueError("Unsupported roadmap topic.")
        if (
            isinstance(duration_months, bool)
            or not isinstance(duration_months, int)
            or not 1 <= duration_months <= 12
        ):
            raise ValueError("Roadmap duration must be between 1 and 12 months.")
        if level not in cls.LEVELS:
            raise ValueError("Unsupported roadmap level.")
        try:
            hours = Decimal(str(daily_hours))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Daily study hours must be numeric.") from exc
        if not Decimal("0.5") <= hours <= Decimal("8.0"):
            raise ValueError("Daily study hours must be between 0.5 and 8.0.")
        if start_date is not None and not isinstance(start_date, date):
            raise ValueError("Roadmap start date must be a date.")
        return hours

    @classmethod
    @transaction.atomic
    def generate_roadmap(
        cls,
        user,
        topic,
        duration_months,
        daily_hours,
        level="beginner",
        start_date=None,
    ):
        """Create one roadmap and exactly `duration_months * 30` days."""
        hours = cls._validated_inputs(
            topic,
            duration_months,
            daily_hours,
            level,
            start_date,
        )
        total_days = duration_months * 30
        topic_name = cls.TOPIC_TEMPLATES[topic]["name"]
        roadmap = Roadmap.objects.create(
            user=user,
            topic=topic,
            title=f"{topic_name} Roadmap",
            description=(
                f"A {duration_months}-month learning path for "
                f"{topic_name} at {level} level."
            ),
            total_days=total_days,
            daily_hours=hours,
            level=level,
            start_date=start_date,
            end_date=(
                start_date + timedelta(days=total_days - 1)
                if start_date
                else None
            ),
        )
        cls._generate_days(
            roadmap,
            topic,
            total_days,
            hours,
            level,
        )
        return roadmap

    @classmethod
    def _generate_days(
        cls,
        roadmap,
        topic,
        total_days,
        daily_hours,
        level,
    ):
        modules = cls.TOPIC_TEMPLATES[topic]["modules"]
        days_per_module, remainder = divmod(total_days, len(modules))
        minimums = {
            "beginner": 3,
            "intermediate": 2,
            "advanced": 1,
        }
        days_per_module = max(days_per_module, minimums[level])

        generated = []
        current_day = 1
        for module_index, module_name in enumerate(modules):
            module_days = days_per_module + (
                1 if module_index < remainder else 0
            )
            for day_in_module in range(1, module_days + 1):
                if current_day > total_days:
                    break
                generated.append(
                    Day(
                        roadmap=roadmap,
                        day_number=current_day,
                        title=cls._generate_day_title(
                            module_name,
                            day_in_module,
                            module_days,
                        ),
                        description=cls._generate_day_description(
                            day_in_module,
                            module_days,
                            level,
                        ),
                        estimated_hours=daily_hours,
                        order=current_day,
                    )
                )
                current_day += 1
            if current_day > total_days:
                break

        if len(generated) != total_days:
            raise RuntimeError("Roadmap day generation did not reach its target.")
        Day.objects.bulk_create(generated)

    @staticmethod
    def _generate_day_title(module_name, day_in_module, total_module_days):
        if total_module_days == 1:
            return module_name
        if day_in_module == 1:
            return f"{module_name}: Introduction"
        if day_in_module == total_module_days:
            return f"{module_name}: Practice & Review"
        return f"{module_name}: Part {day_in_module}"

    @staticmethod
    def _generate_day_description(
        day_in_module,
        total_module_days,
        level,
    ):
        descriptions = {
            "beginner": {
                "intro": "Learn the fundamentals with examples and basic exercises.",
                "middle": (
                    "Continue learning with hands-on practice and problem-solving."
                ),
                "end": (
                    "Review concepts and complete practice exercises to reinforce "
                    "learning."
                ),
            },
            "intermediate": {
                "intro": "Deep dive into concepts with advanced examples.",
                "middle": "Work on complex problems and real-world applications.",
                "end": "Solve challenging problems and review key concepts.",
            },
            "advanced": {
                "intro": "Master advanced concepts and optimization techniques.",
                "middle": "Work on expert-level problems and edge cases.",
                "end": (
                    "Complete comprehensive review and advanced problem-solving."
                ),
            },
        }
        if total_module_days == 1:
            position = "middle"
        elif day_in_module == 1:
            position = "intro"
        elif day_in_module == total_module_days:
            position = "end"
        else:
            position = "middle"
        return descriptions[level][position]

    @classmethod
    def get_available_topics(cls):
        return [
            {"code": code, "name": data["name"]}
            for code, data in cls.TOPIC_TEMPLATES.items()
        ]

    @staticmethod
    def estimate_completion_date(start_date, duration_months):
        if not start_date:
            return None
        if (
            isinstance(duration_months, bool)
            or not isinstance(duration_months, int)
            or duration_months < 1
        ):
            raise ValueError("Duration must be a positive integer.")
        return start_date + timedelta(days=duration_months * 30 - 1)
