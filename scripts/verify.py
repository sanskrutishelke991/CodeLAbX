#!/usr/bin/env python3
"""Run the local and CI verification gate for CodeLabX."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

SOURCE_DIRECTORIES = [
    "accounts",
    "ai_tools",
    "assessments",
    "challenges",
    "codelabx",
    "content",
    "dashboard",
    "learning",
    "intelligence",
    "notes",
    "practice",
    "progress",
    "scripts",
]


def run(
    label: str,
    command: list[str],
    env: dict[str, str],
) -> None:
    print(
        f"\\n===== {label} =====",
        flush=True,
    )

    subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
    )


def main() -> int:
    env = os.environ.copy()

    env.setdefault(
        "DJANGO_SECRET_KEY",
        (
            "verification-only-not-for-production-"
            + "x" * 64
        ),
    )

    env.setdefault(
        "DJANGO_DEBUG",
        "False",
    )

    env.setdefault(
        "DJANGO_ALLOWED_HOSTS",
        "testserver,localhost,127.0.0.1",
    )

    env.setdefault(
        "AI_FEATURES_ENABLED",
        "False",
    )

    env.setdefault(
        "ASSESSMENTS_ENABLED",
        "False",
    )

    env.setdefault(
        "CODING_CHALLENGES_ENABLED",
        "False",
    )

    env.setdefault(
        "IMAGE_ANALYSIS_ENABLED",
        "False",
    )

    run(
        "Compile Python",
        [
            PYTHON,
            "-m",
            "compileall",
            "-q",
            *SOURCE_DIRECTORIES,
        ],
        env,
    )

    run(
        "Critical lint",
        [
            PYTHON,
            "-m",
            "ruff",
            "check",
            ".",
        ],
        env,
    )

    run(
        "Migration drift",
        [
            PYTHON,
            "manage.py",
            "makemigrations",
            "--check",
            "--dry-run",
        ],
        env,
    )

    run(
        "Django check",
        [
            PYTHON,
            "manage.py",
            "check",
        ],
        env,
    )

    run(
        "Coverage reset",
        [
            PYTHON,
            "-m",
            "coverage",
            "erase",
        ],
        env,
    )

    run(
        "Tests",
        [
            PYTHON,
            "-m",
            "coverage",
            "run",
            "manage.py",
            "test",
            "--verbosity",
            "1",
        ],
        env,
    )

    run(
        "Coverage report",
        [
            PYTHON,
            "-m",
            "coverage",
            "report",
        ],
        env,
    )

    production_env = env.copy()

    production_env.update(
        {
            "DJANGO_DEBUG": "False",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_SECURE_SSL_REDIRECT": "True",
            "DJANGO_SESSION_COOKIE_SECURE": "True",
            "DJANGO_CSRF_COOKIE_SECURE": "True",
            "DJANGO_HSTS_SECONDS": "31536000",
            "DJANGO_HSTS_INCLUDE_SUBDOMAINS": "True",
            "DJANGO_HSTS_PRELOAD": "True",
            "DJANGO_USE_WHITENOISE": "True",
        }
    )

    run(
        "Production static collection",
        [
            PYTHON,
            "manage.py",
            "collectstatic",
            "--noinput",
            "--clear",
            "--verbosity",
            "0",
        ],
        production_env,
    )

    run(
        "Production deployment check",
        [
            PYTHON,
            "manage.py",
            "check",
            "--deploy",
        ],
        production_env,
    )

    run(
        "Dependency audit",
        [
            PYTHON,
            "-m",
            "pip_audit",
            "-r",
            "requirements/prod.txt",
            "--progress-spinner",
            "off",
        ],
        env,
    )

    print(
        "\n===== ALL GATE A CHECKS PASSED ====="
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
