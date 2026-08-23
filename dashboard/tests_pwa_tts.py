from __future__ import annotations

import json
import re
from pathlib import Path

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent


class PWAAssetTests(SimpleTestCase):
    def test_manifest_is_local_installable_and_has_real_icons(self):
        manifest = json.loads(
            (ROOT / "static" / "manifest.webmanifest").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["id"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#6c5ce7")
        self.assertNotIn("http://", json.dumps(manifest))
        self.assertNotIn("https://", json.dumps(manifest))
        sizes = set()
        for icon in manifest["icons"]:
            relative = icon["src"].removeprefix("/static/")
            path = ROOT / "static" / relative
            self.assertTrue(path.is_file())
            with Image.open(path) as image:
                sizes.add(image.size)
                self.assertEqual(image.format, "PNG")
            self.assertIn("maskable", icon["purpose"])
        self.assertIn((192, 192), sizes)
        self.assertIn((512, 512), sizes)

    def test_service_worker_precaches_only_public_shell_and_static_assets(self):
        source = (
            ROOT / "static" / "js" / "service-worker.js"
        ).read_text(encoding="utf-8")
        self.assertIn('fetch(request, {cache: "no-store"})', source)
        self.assertIn('request.mode === "navigate"', source)
        self.assertIn('url.pathname.startsWith("/static/")', source)
        self.assertIn('caches.match("/offline/")', source)
        for private_path in (
            "/accounts/",
            "/dashboard/",
            "/intelligence/",
            "/ai-tools/",
            "/media/",
        ):
            self.assertNotIn(f'"{private_path}"', source)
        shell_paths = re.findall(r'^\s+"(/(?:offline|static)/[^\"]*)"', source, re.M)
        self.assertGreater(len(shell_paths), 10)
        for public_path in shell_paths:
            if public_path == "/offline/":
                continue
            relative = public_path.removeprefix("/static/")
            self.assertTrue(
                (ROOT / "static" / relative).is_file(),
                msg=f"Missing precache asset: {public_path}",
            )

    def test_registration_uses_root_worker_and_user_gesture_install_prompt(self):
        source = (ROOT / "static" / "js" / "pwa.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('register("/service-worker.js", {scope: "/"})', source)
        self.assertIn("beforeinstallprompt", source)
        self.assertIn("deferredInstallPrompt.prompt()", source)
        self.assertIn("userChoice", source)
        self.assertNotIn("fetch(", source)


class TextToSpeechAssetTests(SimpleTestCase):
    def test_tts_is_bounded_browser_only_and_uses_text_content(self):
        source = (ROOT / "static" / "js" / "tts.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("SpeechSynthesisUtterance", source)
        self.assertIn("speechSynthesis", source)
        self.assertIn("MAX_SPEAK_CHARS = 12000", source)
        self.assertIn("CHUNK_SIZE = 220", source)
        self.assertIn("clone.textContent", source)
        self.assertIn("[data-tts-ignore]", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("MediaRecorder", source)
        self.assertNotIn("getUserMedia", source)

    def test_tts_stores_only_voice_and_rate_preferences(self):
        source = (ROOT / "static" / "js" / "tts.js").read_text(
            encoding="utf-8"
        )
        storage_keys = set(
            re.findall(r'codelabx-tts-[a-z-]+', source)
        )
        self.assertEqual(
            storage_keys,
            {"codelabx-tts-rate", "codelabx-tts-voice"},
        )

    def test_base_uses_static_pwa_and_tts_scripts_without_inline_code(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        controls = (
            ROOT / "templates" / "partials" / "tts_controls.html"
        ).read_text(encoding="utf-8")
        combined = base + controls
        self.assertIn("manifest.webmanifest", base)
        self.assertIn("pwa-180.png", base)
        self.assertIn('id="pwaInstallButton"', base)
        self.assertIn('id="ttsToggleButton"', base)
        self.assertIn('id="ttsPanel"', controls)
        self.assertIn("no audio upload", controls)
        self.assertIn("js/pwa.js", base)
        self.assertIn("js/tts.js", base)
        self.assertIsNone(
            re.search(r"<script(?![^>]*\bsrc\s*=)[^>]*>", combined, re.I)
        )
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", combined, re.I))


class PWARouteTests(TestCase):
    def test_root_service_worker_has_safe_scope_and_update_headers(self):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/javascript"))
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "codelabx-public-shell-v1")

    def test_offline_page_is_public_generic_and_cache_safe(self):
        user = User.objects.create_user(
            username="offline-private-user",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private dashboards")
        self.assertContains(response, "intentionally not cached")
        self.assertNotContains(response, user.username)
        self.assertIn("public", response["Cache-Control"])
        self.assertNotIn("chatWidget", response.content.decode())

    def test_landing_renders_install_and_tts_controls(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'id="pwaInstallButton"')
        self.assertContains(response, 'id="ttsPanel"')
