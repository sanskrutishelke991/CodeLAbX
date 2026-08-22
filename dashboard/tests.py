import hashlib
import json
import re
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from challenges.models import Challenge


class RouteSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='smoke-user',
            password='StrongPass123!',
        )

    def test_public_pages_render(self):
        routes = [
            'landing',
            'accounts:login',
            'accounts:register',
        ]

        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name)
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_authenticated_pages_render(self):
        self.client.force_login(self.user)

        routes = [
            'dashboard:home',
            'accounts:profile',
            'accounts:profile_edit',
            'accounts:settings',
            'learning:roadmaps',
            'learning:roadmap_create',
            'content:library',
            'content:my_videos',
            'practice:task_list',
            'practice:examiner',
            'assessments:quiz_list',
            'assessments:create',
            'ai_tools:home',
            'ai_tools:image_analyzer',
            'ai_tools:image_history',
            'progress:achievements',
            'progress:leaderboard',
            'progress:analytics',
            'notes:list',
            'notes:create',
            'notes:bookmarks',
            'intelligence:onboarding',
        ]

        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name)
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    @patch(
        'challenges.views.'
        'get_or_create_today_challenges'
    )
    def test_challenge_dashboard_without_ai_call(
        self,
        generator,
    ):
        generator.return_value = (
            Challenge.objects.none()
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse('challenges:dashboard')
        )

        self.assertEqual(response.status_code, 200)


from django.contrib import admin
from accounts.models import UserProfile
from assessments.models import Test
from challenges.models import Challenge
from content.models import Video
from learning.models import Roadmap
from notes.models import Note
from practice.models import CodeReview
from progress.models import XPTransaction


class AdminRegistrationTests(TestCase):
    def test_operational_models_are_registered(self):
        for model in [
            UserProfile,
            Test,
            Challenge,
            Video,
            Roadmap,
            Note,
            CodeReview,
            XPTransaction,
        ]:
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)


from django.utils import timezone
from learning.models import Day, Roadmap
from progress.models import DailyActivity, UserBadge, Badge, XPTransaction


class DashboardTruthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="truth-dashboard-user",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

    def test_dashboard_uses_recorded_values(self):
        roadmap = Roadmap.objects.create(
            user=self.user,
            topic="ML",
            title="Truth roadmap",
            total_days=2,
            daily_hours=1,
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=1,
            title="Completed",
            estimated_hours=1,
            order=1,
            is_completed=True,
            completed_at=timezone.now(),
        )
        Day.objects.create(
            roadmap=roadmap,
            day_number=2,
            title="Next",
            estimated_hours=1,
            order=2,
        )
        DailyActivity.objects.create(
            user=self.user,
            date=timezone.localdate(),
            minutes_studied=60,
            days_completed=1,
        )
        badge = Badge.objects.create(
            name="Truth badge",
            description="Actually earned",
            icon="T",
            category="learning",
            rarity="common",
            xp_reward=1,
            requirement_type="topics_completed",
            requirement_value=1,
        )
        UserBadge.objects.create(user=self.user, badge=badge)
        XPTransaction.objects.create(
            user=self.user,
            amount=20,
            event_type="day-completed",
            reason="Completed a real day",
            idempotency_key="truth-event",
        )

        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Truth roadmap")
        self.assertContains(response, "Truth badge")
        self.assertContains(response, "Completed a real day")
        self.assertContains(response, "1 active days")

    def test_dashboard_template_has_no_random_demo_data(self):
        template = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / "dashboard"
            / "home.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Math.random", template)
        self.assertNotIn("127</div>", template)
        self.assertNotIn("Completed Day 5 of ML Roadmap", template)
        self.assertNotIn("Try Neural Networks next", template)
        self.assertNotIn("Lofi Beats to Study", template)

    def test_heatmap_contains_exactly_365_days(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(len(response.context["heatmap_data"]), 365)


class OperationalSecurityTests(TestCase):
    def test_liveness_endpoint_has_no_dependency_checks(self):
        response = self.client.get(reverse("live"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "alive"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_health_endpoint_checks_database_and_cache(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "healthy",
                "database": "ok",
                "cache": "ok",
            },
        )
        self.assertEqual(response["Cache-Control"], "no-store")

    @patch("codelabx.views.cache.set", side_effect=RuntimeError("offline"))
    def test_health_endpoint_fails_closed_when_cache_is_unavailable(self, cache_set):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["cache"], "unavailable")
        self.assertEqual(response.json()["database"], "ok")

    def test_security_headers_are_present(self):
        response = self.client.get(reverse("landing"))
        self.assertIn("Permissions-Policy", response)
        self.assertEqual(response["X-Permitted-Cross-Domain-Policies"], "none")
        self.assertEqual(response["X-DNS-Prefetch-Control"], "off")
        self.assertIn("Content-Security-Policy", response)
        self.assertNotIn("Content-Security-Policy-Report-Only", response)
        policy = response["Content-Security-Policy"]
        directives = {
            part.strip().split(" ", 1)[0]: part.strip()
            for part in policy.split(";")
            if part.strip()
        }
        self.assertEqual(directives["script-src"], "script-src 'self'")
        self.assertEqual(
            directives["script-src-attr"],
            "script-src-attr 'none'",
        )
        self.assertNotIn("'unsafe-inline'", directives["style-src"])
        self.assertEqual(
            directives["style-src-attr"],
            "style-src-attr 'unsafe-inline'",
        )

    def test_obsolete_backup_files_are_removed(self):
        repository = Path(__file__).resolve().parent.parent
        patterns = ["*.backup", "*.old", "*.before_*", "*.pre_*"]
        found = []
        for pattern in patterns:
            found.extend(repository.rglob(pattern))
        self.assertEqual(found, [])


class AccessibilityAndLegalTests(TestCase):
    def test_base_has_skip_link_and_main_target(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, 'class="skip-link"')
        base = (Path(__file__).resolve().parent.parent / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn('id="main-content"', base)
        base_css = (Path(__file__).resolve().parent.parent / "static" / "css" / "base.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", base_css)
        self.assertIn("aria-expanded", base)

    def test_legal_pages_render(self):
        self.assertEqual(self.client.get(reverse("dashboard:privacy")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:terms")).status_code, 200)

    def test_landing_does_not_make_old_false_privacy_claims(self):
        landing = (Path(__file__).resolve().parent.parent / "templates" / "landing.html").read_text(encoding="utf-8")
        self.assertNotIn("We never sell or share your data with third parties", landing)
        self.assertNotIn("industry-standard encryption", landing)
        self.assertIn("Google Gemini", landing)

    def test_legacy_omnitrix_css_is_removed(self):
        base = (Path(__file__).resolve().parent.parent / "templates" / "base.html").read_text(encoding="utf-8")
        base_css = (Path(__file__).resolve().parent.parent / "static" / "css" / "base.css").read_text(encoding="utf-8")
        self.assertNotIn(".omnitrix-overlay", base_css)
        self.assertIn(".omni-dial", base_css)

class FrontendTrustTests(TestCase):
    def setUp(self):
        self.repository = Path(__file__).resolve().parent.parent

    def test_browser_dependencies_are_local_and_versioned(self):
        checked_templates = [
            self.repository / "templates" / "base.html",
            self.repository / "templates" / "landing.html",
            self.repository / "templates" / "progress" / "analytics.html",
        ]
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in checked_templates
        )
        self.assertNotIn("cdn.jsdelivr.net", combined)
        self.assertNotIn("fonts.googleapis.com", combined)
        self.assertNotIn("fonts.gstatic.com", combined)

        manifest_path = self.repository / "static" / "vendor" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["bootstrap"]["version"], "5.3.8")
        self.assertEqual(manifest["bootstrap-icons"]["version"], "1.13.1")
        self.assertEqual(manifest["chart.js"]["version"], "4.5.1")
        for relative_path, expected_digest in manifest["sha256"].items():
            asset = self.repository / "static" / "vendor" / relative_path
            self.assertTrue(asset.is_file())
            self.assertGreater(asset.stat().st_size, 1000)
            self.assertEqual(
                hashlib.sha256(asset.read_bytes()).hexdigest(),
                expected_digest,
            )

    def test_base_and_landing_styles_and_scripts_are_static(self):
        for relative_path in ["templates/base.html", "templates/landing.html"]:
            source = (self.repository / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("<style>", source)
            self.assertIsNone(
                re.search(r"<script(?![^>]*src\s*=)[^>]*>", source)
            )

    def test_templates_have_no_empty_fragment_links(self):
        empty_links = []
        for template in (self.repository / "templates").rglob("*.html"):
            source = template.read_text(encoding="utf-8")
            if re.search(r"href\s*=\s*[\"']#[\"']", source):
                empty_links.append(str(template.relative_to(self.repository)))
        self.assertEqual(empty_links, [])

    def test_landing_avoids_unverified_scale_and_pricing_claims(self):
        landing = (
            self.repository / "templates" / "landing.html"
        ).read_text(encoding="utf-8")
        for unsupported_claim in [
            "Free forever",
            "100% free",
            "Trusted by 1000+ learners",
            "Join thousands of learners",
            "senior developer reviewing your code 24/7",
            "mobile app is coming soon",
            "actually understands you",
            "instant code reviews",
            "adapt to your pace",
            "growth, and predictions",
            "No waiting, just learning",
            "codelabx.com/dashboard",
        ]:
            self.assertNotIn(unsupported_claim, landing)
        self.assertIn("Development preview", landing)
        self.assertIn("not a correctness verdict", landing)

        toolbox = (
            self.repository / "templates" / "ai_tools" / "home.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("24/7", toolbox)
        self.assertNotIn(">∞<", toolbox)
        self.assertNotIn("every single day", toolbox)
        self.assertNotIn("Powerful AI features", toolbox)
        self.assertNotIn(">Popular<", toolbox)
        self.assertIn("Default quota", toolbox)


class FrontendExtractionBudgetTests(TestCase):
    def test_page_assets_are_static_and_inline_debt_only_decreases(self):
        repository = Path(__file__).resolve().parent.parent
        templates = list((repository / "templates").rglob("*.html"))
        style_blocks = 0
        inline_scripts = 0
        event_handlers = 0
        style_attributes = 0
        affected_templates = 0

        for template in templates:
            source = template.read_text(encoding="utf-8")
            styles = len(re.findall(r"<style(?:\s|>)", source, re.I))
            scripts = len(
                re.findall(
                    r"<script(?![^>]*\bsrc\s*=)[^>]*>",
                    source,
                    re.I,
                )
            )
            handlers = len(
                re.findall(r"\son[a-z]+\s*=", source, re.I)
            )
            inline_styles = len(
                re.findall(r"\sstyle\s*=", source, re.I)
            )
            style_blocks += styles
            inline_scripts += scripts
            event_handlers += handlers
            style_attributes += inline_styles
            if styles or scripts or handlers:
                affected_templates += 1

        self.assertEqual(style_blocks, 0)
        self.assertEqual(inline_scripts, 0)
        self.assertEqual(event_handlers, 0)
        self.assertLessEqual(style_attributes, 201)
        self.assertEqual(affected_templates, 0)

        page_css = list((repository / "static" / "css" / "pages").glob("*.css"))
        page_js = list((repository / "static" / "js" / "pages").glob("*.js"))
        self.assertEqual(len(page_css), 38)
        self.assertEqual(len(page_js), 20)
        for asset in page_css + page_js:
            source = asset.read_text(encoding="utf-8")
            self.assertNotIn("{%", source)
            self.assertNotIn("{{", source)

    def test_destructive_forms_use_shared_confirmation_hook(self):
        repository = Path(__file__).resolve().parent.parent
        paths = [
            "templates/accounts/settings.html",
            "templates/learning/roadmap_detail.html",
            "templates/notes/bookmarks_list.html",
            "templates/notes/notes_list.html",
        ]
        for relative_path in paths:
            source = (repository / relative_path).read_text(encoding="utf-8")
            self.assertIn("data-confirm=", source)
            self.assertNotIn("onsubmit=", source)
        base_js = (repository / "static" / "js" / "base.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('form[data-confirm]', base_js)

    def test_first_migrated_interactions_have_no_inline_handlers(self):
        repository = Path(__file__).resolve().parent.parent
        migrated = [
            "templates/ai_tools/image_history.html",
            "templates/assessments/quiz_list.html",
            "templates/learning/roadmap_create.html",
            "templates/learning/roadmap_list.html",
            "templates/notes/notes_list.html",
            "templates/practice/code_examiner.html",
        ]
        for relative_path in migrated:
            source = (repository / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIsNone(
                    re.search(r"\son[a-z]+\s*=", source, re.I)
                )


class DashboardQueryBudgetTests(TestCase):
    def test_dashboard_query_count_stays_bounded_with_many_roadmaps(self):
        user = User.objects.create_user(
            username="dashboard-query-user",
            password="StrongPass123!",
        )
        for index in range(12):
            roadmap = Roadmap.objects.create(
                user=user,
                topic="ML",
                title=f"Roadmap {index}",
                total_days=2,
                daily_hours=1,
            )
            Day.objects.create(
                roadmap=roadmap,
                day_number=1,
                title="First day",
                estimated_hours=1,
                order=1,
                is_completed=True,
                completed_at=timezone.now(),
            )
            Day.objects.create(
                roadmap=roadmap,
                day_number=2,
                title="Next day",
                estimated_hours=1,
                order=2,
            )

        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(queries),
            25,
            msg=f"Dashboard exceeded query budget: {len(queries)}",
        )


class DocumentationTruthTests(TestCase):
    def test_project_documents_describe_the_current_system(self):
        repository = Path(__file__).resolve().parent.parent
        document_paths = [
            repository / "docs" / "ARCHITECTURE.md",
            repository / "docs" / "DB_SCHEMA.md",
            repository / "docs" / "PRD.md",
            repository / "docs" / "TASKS.md",
            repository / "docs" / "UI_PLAN.md",
            repository / "DESIGN_SYSTEM_MIGRATION.md",
        ]
        documents = "\n".join(
            path.read_text(encoding="utf-8")
            for path in document_paths
        )
        for stale_claim in [
            "Django 4.x",
            "Python 3.8+",
            "OpenAI API",
            "### users App",
            "### roadmaps App",
            "future mobile app development",
            "**Total Duration**: 3-4 months",
            "No External APIs",
            "Phase 3: Microservices",
        ]:
            self.assertNotIn(stale_claim, documents)

        for current_fact in [
            "Django 6.0.8",
            "Google Gemini",
            "XPTransaction",
            "PostgreSQL",
            "Redis",
            "not a public production",
        ]:
            self.assertIn(current_fact, documents)

        for path in document_paths:
            source = path.read_text(encoding="utf-8")
            self.assertIn("Last reviewed: 2026-08-08", source)


class LegacyQualityRegressionTests(TestCase):
    def test_hardened_legacy_modules_have_no_bare_except_or_print(self):
        repository = Path(__file__).resolve().parent.parent
        for relative_path in [
            "learning/views.py",
            "progress/services.py",
            "progress/views.py",
            "notes/views.py",
            "practice/views.py",
        ]:
            source = (repository / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIsNone(re.search(r"except\s*:\s*", source))
                self.assertNotIn("print(", source)
                self.assertNotIn("str(e)", source)
