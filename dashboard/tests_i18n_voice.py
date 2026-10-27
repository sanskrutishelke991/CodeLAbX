from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


ROOT = Path(__file__).resolve().parent.parent


class MultilingualConfigurationTests(SimpleTestCase):
    def test_supported_languages_and_locale_middleware_are_configured(self):
        self.assertEqual(
            dict(settings.LANGUAGES),
            {"en": "English", "hi": "हिन्दी", "mr": "मराठी"},
        )
        session_index = settings.MIDDLEWARE.index(
            "django.contrib.sessions.middleware.SessionMiddleware"
        )
        locale_index = settings.MIDDLEWARE.index(
            "django.middleware.locale.LocaleMiddleware"
        )
        common_index = settings.MIDDLEWARE.index(
            "django.middleware.common.CommonMiddleware"
        )
        self.assertLess(session_index, locale_index)
        self.assertLess(locale_index, common_index)
        self.assertIn(ROOT / "locale", list(settings.LOCALE_PATHS))

    def test_hindi_and_marathi_catalogs_include_compiled_core_controls(self):
        for language in ("hi", "mr"):
            with self.subTest(language=language):
                directory = ROOT / "locale" / language / "LC_MESSAGES"
                po = directory / "django.po"
                mo = directory / "django.mo"
                self.assertTrue(po.is_file())
                self.assertTrue(mo.is_file())
                self.assertGreater(mo.stat().st_size, 1000)
                source = po.read_text(encoding="utf-8")
                self.assertIn('msgid "Interface language"', source)
                self.assertIn('msgid "Voice coding input"', source)
                self.assertIn('msgid "CodeLabX cannot reach the server"', source)

    def test_language_selector_is_post_csrf_and_has_no_inline_handler(self):
        source = (
            ROOT / "templates" / "partials" / "language_selector.html"
        ).read_text(encoding="utf-8")
        self.assertIn('method="post"', source)
        self.assertIn("{% csrf_token %}", source)
        self.assertIn("set_language", source)
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", source, re.I))


class MultilingualFlowTests(TestCase):
    def test_hindi_selection_translates_real_landing_controls(self):
        response = self.client.post(
            reverse("set_language"),
            {"language": "hi", "next": reverse("landing")},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="hi"', html=False)
        self.assertContains(response, "साइन इन")
        self.assertContains(response, "शुरू करें")
        self.assertContains(response, "वॉइस कोडिंग इनपुट")
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, "hi")

    def test_marathi_selection_translates_offline_and_accessibility_controls(self):
        self.client.post(
            reverse("set_language"),
            {"language": "mr", "next": reverse("offline")},
        )
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="mr"', html=False)
        self.assertContains(response, "ऑफलाइन")
        self.assertContains(response, "पुन्हा प्रयत्न करा")

    def test_unsupported_language_does_not_activate_unlisted_locale(self):
        self.client.post(
            reverse("set_language"),
            {"language": "xx", "next": reverse("landing")},
        )
        response = self.client.get(reverse("landing"))
        self.assertNotContains(response, '<html lang="xx"', html=False)
        cookie = self.client.cookies.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie is not None:
            self.assertNotEqual(cookie.value, "xx")


class VoiceCodingInputTests(SimpleTestCase):
    def test_voice_input_is_bounded_browser_only_and_never_records_audio(self):
        source = (ROOT / "static" / "js" / "voice-input.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("SpeechRecognition", source)
        self.assertIn("webkitSpeechRecognition", source)
        self.assertIn("MAX_TRANSCRIPT_CHARS = 4000", source)
        self.assertIn("MAX_RESULT_CHARS = 500", source)
        self.assertIn("setRangeText", source)
        self.assertIn("not-allowed", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("MediaRecorder", source)
        self.assertNotIn("getUserMedia", source)
        self.assertNotIn("localStorage", source)

    def test_voice_commands_cover_code_punctuation_and_three_languages(self):
        source = (ROOT / "static" / "js" / "voice-input.js").read_text(
            encoding="utf-8"
        )
        for command in (
            '"new line"',
            '"indent"',
            '"open parenthesis"',
            '"double equals"',
            '"नई लाइन"',
            '"नवीन ओळ"',
            '"सुनना बंद करो"',
            '"ऐकणे थांबवा"',
        ):
            self.assertIn(command, source)
        self.assertIn('new Set(["text", "search", "url", "email"])', source)
        self.assertNotIn('"password"', source)

    def test_voice_controls_are_static_accessible_and_pwa_cached(self):
        partial = (
            ROOT / "templates" / "partials" / "voice_controls.html"
        ).read_text(encoding="utf-8")
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        landing = (ROOT / "templates" / "landing.html").read_text(
            encoding="utf-8"
        )
        worker = (
            ROOT / "static" / "js" / "service-worker.js"
        ).read_text(encoding="utf-8")
        self.assertIn('id="voicePanel"', partial)
        self.assertIn("explicit permission", partial)
        self.assertIn("does not record or store microphone audio", partial)
        self.assertIn('id="voiceToggleButton"', base)
        self.assertIn('id="voiceToggleButton"', landing)
        self.assertIn("js/voice-input.js", base)
        self.assertIn("js/voice-input.js", landing)
        self.assertIn("/static/js/voice-input.js", worker)
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", partial, re.I))

    def test_privacy_page_discloses_browser_vendor_processing(self):
        privacy = (ROOT / "templates" / "legal" / "privacy.html").read_text(
            encoding="utf-8"
        )
        normalized = re.sub(r"\s+", " ", privacy)
        self.assertIn("browser or operating-system speech provider", normalized)
        self.assertIn("does not store microphone audio", normalized)
