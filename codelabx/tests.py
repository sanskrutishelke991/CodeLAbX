from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from .configuration import build_cache_settings, build_database_settings
from scripts.load_smoke import percentile, validate_target

from .readiness import collect_production_findings


class LoadSmokeSafetyTests(SimpleTestCase):
    def test_remote_targets_require_explicit_permission(self):
        with self.assertRaisesRegex(ValueError, "--allow-remote"):
            validate_target("https://example.com/health/", allow_remote=False)
        self.assertEqual(
            validate_target(
                "https://example.com/health/",
                allow_remote=True,
            ),
            "https://example.com/health/",
        )

    def test_credentials_are_rejected_from_target_urls(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            validate_target(
                "https://user:secret@example.com/health/",
                allow_remote=True,
            )

    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(percentile([10, 20, 30, 40], 0.50), 20)
        self.assertEqual(percentile([10, 20, 30, 40], 0.95), 40)


class InfrastructureConfigurationTests(SimpleTestCase):
    def test_sqlite_remains_the_default(self):
        databases = build_database_settings(
            base_dir=Path("/srv/codelabx"),
            database_url="",
            sqlite_path="db.sqlite3",
            connection_max_age=60,
            connect_timeout=10,
        )
        self.assertEqual(
            databases["default"]["ENGINE"],
            "django.db.backends.sqlite3",
        )
        self.assertEqual(
            databases["default"]["NAME"],
            Path("/srv/codelabx/db.sqlite3"),
        )

    def test_postgresql_url_is_parsed_without_losing_encoded_credentials(self):
        databases = build_database_settings(
            base_dir=Path("/srv/codelabx"),
            database_url=(
                "postgresql://learner:p%40ss@db.example.com:5433/"
                "codelabx?sslmode=verify-full"
            ),
            sqlite_path="db.sqlite3",
            connection_max_age=90,
            connect_timeout=7,
        )
        database = databases["default"]
        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["USER"], "learner")
        self.assertEqual(database["PASSWORD"], "p@ss")
        self.assertEqual(database["HOST"], "db.example.com")
        self.assertEqual(database["PORT"], "5433")
        self.assertEqual(database["CONN_MAX_AGE"], 90)
        self.assertTrue(database["CONN_HEALTH_CHECKS"])
        self.assertEqual(database["OPTIONS"]["sslmode"], "verify-full")
        self.assertEqual(database["OPTIONS"]["connect_timeout"], 7)

    def test_database_url_rejects_unsupported_or_ambiguous_options(self):
        invalid_urls = [
            "mysql://user:pass@db.example.com/codelabx",
            "postgresql://user:pass@db.example.com/codelabx?unknown=yes",
            "postgresql://user:pass@db.example.com/codelabx?sslmode=require&sslmode=prefer",
            "postgresql://user:pass@db.example.com/codelabx?sslmode=invalid",
        ]
        for database_url in invalid_urls:
            with self.subTest(database_url=database_url):
                with self.assertRaises(ImproperlyConfigured):
                    build_database_settings(
                        base_dir=Path("/srv/codelabx"),
                        database_url=database_url,
                        sqlite_path="db.sqlite3",
                        connection_max_age=60,
                        connect_timeout=10,
                    )

    def test_local_cache_remains_the_default(self):
        caches = build_cache_settings(
            redis_url="",
            key_prefix="codelabx",
            default_timeout=300,
            socket_timeout=5,
        )
        self.assertEqual(
            caches["default"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_redis_cache_is_shared_and_bounded(self):
        caches = build_cache_settings(
            redis_url="rediss://:secret@cache.example.com:6380/1",
            key_prefix="codelabx-prod",
            default_timeout=600,
            socket_timeout=4,
        )
        cache = caches["default"]
        self.assertEqual(
            cache["BACKEND"],
            "django.core.cache.backends.redis.RedisCache",
        )
        self.assertEqual(cache["TIMEOUT"], 600)
        self.assertEqual(cache["OPTIONS"]["socket_timeout"], 4)
        self.assertNotIn("IGNORE_EXCEPTIONS", cache["OPTIONS"])

    def test_redis_url_and_prefix_are_validated(self):
        invalid_values = [
            ("http://cache.example.com/1", "codelabx"),
            ("redis:///1", "codelabx"),
            ("redis://cache.example.com/1#fragment", "codelabx"),
            ("redis://cache.example.com/1", "bad prefix"),
        ]
        for redis_url, prefix in invalid_values:
            with self.subTest(redis_url=redis_url, prefix=prefix):
                with self.assertRaises(ImproperlyConfigured):
                    build_cache_settings(
                        redis_url=redis_url,
                        key_prefix=prefix,
                        default_timeout=300,
                        socket_timeout=5,
                    )


class ProductionPreflightTests(SimpleTestCase):
    def test_local_configuration_reports_backend_blockers(self):
        config = SimpleNamespace(
            DEBUG=True,
            SECRET_KEY="replace-with-a-long-random-secret",
            ALLOWED_HOSTS=["localhost"],
            CSRF_TRUSTED_ORIGINS=[],
            SECURE_SSL_REDIRECT=False,
            SESSION_COOKIE_SECURE=False,
            CSRF_COOKIE_SECURE=False,
            RATE_LIMIT_ENABLED=True,
            SECURE_HSTS_SECONDS=0,
            SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
            SECURE_HSTS_PRELOAD=False,
            DATABASES={
                "default": {"ENGINE": "django.db.backends.sqlite3"}
            },
            DATABASE_REQUIRE_TLS=True,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"
                }
            },
            REDIS_REQUIRE_TLS=True,
            USE_WHITENOISE=False,
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage"
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                },
            },
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
            DEFAULT_FROM_EMAIL="CodeLabX <noreply@localhost>",
            AI_FEATURES_ENABLED=False,
            ASSESSMENTS_ENABLED=False,
            CODING_CHALLENGES_ENABLED=False,
            IMAGE_ANALYSIS_ENABLED=False,
            GEMINI_API_KEY=None,
            CSP_LEGACY_INLINE_ALLOWED=True,
            TRUST_X_FORWARDED_PROTO=False,
        )
        codes = {
            item.code
            for item in collect_production_findings(config)
            if item.severity == "error"
        }
        self.assertTrue(
            {"PRD001", "PRD010", "PRD012", "PRD014"}.issubset(codes)
        )

    def test_provider_neutral_production_configuration_clears_errors(self):
        config = SimpleNamespace(
            DEBUG=False,
            SECRET_KEY="s" * 80,
            ALLOWED_HOSTS=["learn.example.com"],
            CSRF_TRUSTED_ORIGINS=["https://learn.example.com"],
            SECURE_SSL_REDIRECT=True,
            SESSION_COOKIE_SECURE=True,
            CSRF_COOKIE_SECURE=True,
            RATE_LIMIT_ENABLED=True,
            SECURE_HSTS_SECONDS=31_536_000,
            SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
            SECURE_HSTS_PRELOAD=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "OPTIONS": {"sslmode": "verify-full"},
                }
            },
            DATABASE_REQUIRE_TLS=True,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": "rediss://cache.example.com/1",
                }
            },
            REDIS_REQUIRE_TLS=True,
            USE_WHITENOISE=True,
            STORAGES={
                "default": {"BACKEND": "project.PrivateObjectStorage"},
                "staticfiles": {
                    "BACKEND": (
                        "whitenoise.storage."
                        "CompressedManifestStaticFilesStorage"
                    )
                },
            },
            EMAIL_BACKEND="project.email.TransactionalBackend",
            DEFAULT_FROM_EMAIL="CodeLabX <noreply@example.com>",
            AI_FEATURES_ENABLED=False,
            ASSESSMENTS_ENABLED=False,
            CODING_CHALLENGES_ENABLED=False,
            IMAGE_ANALYSIS_ENABLED=False,
            GEMINI_API_KEY=None,
            CSP_LEGACY_INLINE_ALLOWED=False,
            TRUST_X_FORWARDED_PROTO=True,
        )
        errors = [
            item
            for item in collect_production_findings(config)
            if item.severity == "error"
        ]
        self.assertEqual(errors, [])

    @override_settings(SECRET_KEY="do-not-print-this-production-secret-" + "x" * 60)
    def test_command_fails_without_printing_secret_values(self):
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("production_preflight", stdout=output, no_color=True)
        self.assertNotIn("do-not-print-this", output.getvalue())
        self.assertIn("Preflight summary", output.getvalue())

    def test_json_command_output_is_machine_readable(self):
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command(
                "production_preflight",
                as_json=True,
                stdout=output,
                no_color=True,
            )
        payload = json.loads(output.getvalue())
        self.assertFalse(payload["ready"])
        self.assertGreater(payload["errors"], 0)
