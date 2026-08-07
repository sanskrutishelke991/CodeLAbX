import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ChatMessage, ChatSession
from .services import GeminiService

from django.template import Context, Template
from django.test import SimpleTestCase

from .rendering import (
    render_ai_markdown,
    sanitize_ai_html,
)


class AIRenderingSecurityTests(SimpleTestCase):
    def test_script_content_is_removed(self):
        result = render_ai_markdown(
            "Safe text"
            "<script>alert('xss')</script>"
            "after"
        )

        self.assertIn("Safe text", result)
        self.assertIn("after", result)
        self.assertNotIn(
            "<script",
            result.lower(),
        )
        self.assertNotIn(
            "alert",
            result.lower(),
        )

    def test_event_handlers_and_images_are_removed(self):
        result = sanitize_ai_html(
            '<img src="x" onerror="alert(1)">'
            '<p onclick="x()">Hello</p>'
        )

        self.assertNotIn(
            "<img",
            result.lower(),
        )
        self.assertNotIn(
            "onerror",
            result.lower(),
        )
        self.assertNotIn(
            "onclick",
            result.lower(),
        )
        self.assertIn(
            "<p>Hello</p>",
            result,
        )

    def test_javascript_links_are_removed(self):
        result = sanitize_ai_html(
            '<a href="javascript:alert(1)">'
            'Unsafe'
            '</a>'
        )

        self.assertIn("Unsafe", result)
        self.assertNotIn(
            "javascript:",
            result.lower(),
        )
        self.assertNotIn(
            "alert(1)",
            result.lower(),
        )

    def test_educational_markdown_is_preserved(self):
        result = render_ai_markdown(
            "## Example\n\n"
            "**Bold**\n\n"
            "```python\n"
            "print('safe')\n"
            "```"
        )

        self.assertIn(
            "<h2>Example</h2>",
            result,
        )
        self.assertIn(
            "<strong>Bold</strong>",
            result,
        )
        self.assertIn(
            "<pre><code",
            result,
        )
        self.assertIn("print", result)

    def test_template_filter_resanitizes_html(self):
        template = Template(
            "{% load ai_content %}"
            "{{ value|safe_ai_html }}"
        )

        result = template.render(
            Context(
                {
                    "value": (
                        "<p>Lesson</p>"
                        "<script>steal()</script>"
                    )
                }
            )
        )

        self.assertIn(
            "<p>Lesson</p>",
            result,
        )
        self.assertNotIn(
            "script",
            result.lower(),
        )
        self.assertNotIn(
            "steal",
            result.lower(),
        )


class _FakeModels:
    def __init__(self, text):
        self.text = text

    def generate_content(self, **kwargs):
        return SimpleNamespace(
            text=self.text
        )


def _service_with_response(text):
    service = object.__new__(
        GeminiService
    )

    service.model_name = "test-model"

    service.client = SimpleNamespace(
        models=_FakeModels(text)
    )

    return service


class AIServiceSanitizationTests(SimpleTestCase):
    def test_theory_response_is_sanitized(self):
        service = _service_with_response(
            "# Lesson\n"
            "<script>steal()</script>"
            "<p onclick='x()'>Safe</p>"
        )

        result = service.generate_theory(
            "Python"
        )

        self.assertTrue(result["success"])

        self.assertIn(
            "Lesson",
            result["content_html"],
        )

        self.assertNotIn(
            "script",
            result["content_html"].lower(),
        )

        self.assertNotIn(
            "onclick",
            result["content_html"].lower(),
        )

    def test_chat_response_is_sanitized(self):
        service = _service_with_response(
            "Hello "
            "<img src=x onerror=steal()>"
        )

        result = service.chat("hello")

        self.assertTrue(result["success"])

        self.assertIn(
            "Hello",
            result["response_html"],
        )

        self.assertNotIn(
            "<img",
            result["response_html"].lower(),
        )

        self.assertNotIn(
            "onerror",
            result["response_html"].lower(),
        )


class ChatHistorySanitizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="chat-security-user",
            password="StrongPass123!",
        )

        self.session = ChatSession.objects.create(
            user=self.user
        )

        ChatMessage.objects.create(
            session=self.session,
            role="assistant",
            content=(
                "<p>Answer</p>"
                "<script>steal()</script>"
            ),
        )

        self.client.force_login(self.user)

    def test_assistant_history_is_sanitized(self):
        response = self.client.get(
            reverse(
                "ai_tools:chat_session",
                args=[self.session.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payload = json.loads(
            response.content
        )

        html = (
            payload["messages"][0]
            ["content_html"]
        )

        self.assertIn("Answer", html)

        self.assertNotIn(
            "script",
            html.lower(),
        )

        self.assertNotIn(
            "steal",
            html.lower(),
        )


from django.core.cache import cache
from django.http import JsonResponse
from django.test import RequestFactory, override_settings

from .security import protect_ai_endpoint


class AIRequestGuardTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def request(self):
        request = self.factory.post(
            "/guard-test/"
        )

        request.user = SimpleNamespace(
            is_authenticated=True,
            pk=42,
        )

        return request

    @override_settings(
        AI_FEATURES_ENABLED=False
    )
    def test_disabled_feature_fails_closed(self):
        @protect_ai_endpoint(
            "test",
            "AI_CHAT_BURST_LIMIT",
        )
        def view(request):
            return JsonResponse(
                {"success": True}
            )

        response = view(
            self.request()
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "FEATURE_DISABLED",
        )

    @override_settings(
        AI_FEATURES_ENABLED=True,
        RATE_LIMIT_ENABLED=True,
        AI_CHAT_BURST_LIMIT=2,
        AI_DAILY_REQUEST_LIMIT=20,
        AI_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    def test_burst_limit_returns_429(self):
        @protect_ai_endpoint(
            "burst-test",
            "AI_CHAT_BURST_LIMIT",
        )
        def view(request):
            return JsonResponse(
                {"success": True}
            )

        self.assertEqual(
            view(self.request()).status_code,
            200,
        )

        self.assertEqual(
            view(self.request()).status_code,
            200,
        )

        blocked = view(
            self.request()
        )

        self.assertEqual(
            blocked.status_code,
            429,
        )

        self.assertEqual(
            blocked["Retry-After"],
            "60",
        )

        payload = json.loads(
            blocked.content
        )

        self.assertEqual(
            payload["error_code"],
            "RATE_LIMITED",
        )

    @override_settings(
        AI_FEATURES_ENABLED=True,
        RATE_LIMIT_ENABLED=True,
        AI_CHAT_BURST_LIMIT=20,
        AI_DAILY_REQUEST_LIMIT=2,
        AI_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    def test_daily_limit_shared_across_scopes(self):
        @protect_ai_endpoint(
            "scope-a",
            "AI_CHAT_BURST_LIMIT",
        )
        def first(request):
            return JsonResponse(
                {"success": True}
            )

        @protect_ai_endpoint(
            "scope-b",
            "AI_CHAT_BURST_LIMIT",
        )
        def second(request):
            return JsonResponse(
                {"success": True}
            )

        self.assertEqual(
            first(self.request()).status_code,
            200,
        )

        self.assertEqual(
            second(self.request()).status_code,
            200,
        )

        blocked = first(
            self.request()
        )

        self.assertEqual(
            blocked.status_code,
            429,
        )

        payload = json.loads(
            blocked.content
        )

        self.assertEqual(
            payload["error_code"],
            "DAILY_AI_LIMIT_REACHED",
        )


from unittest.mock import patch


@override_settings(
    AI_FEATURES_ENABLED=True,
    RATE_LIMIT_ENABLED=False,
)
class ChatRequestValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="validated-chat-user",
            password="StrongPass123!",
        )

        self.client.force_login(self.user)

        self.url = reverse(
            "ai_tools:chat_send"
        )

    def post(
        self,
        data,
        content_type="application/json",
    ):
        return self.client.post(
            self.url,
            data=data,
            content_type=content_type,
        )

    def test_malformed_json_is_rejected(self):
        response = self.post("{")

        self.assertEqual(
            response.status_code,
            400,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "INVALID_JSON",
        )

    def test_non_json_content_type_is_rejected(self):
        response = self.post(
            "message=hello",
            "text/plain",
        )

        self.assertEqual(
            response.status_code,
            415,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "UNSUPPORTED_MEDIA_TYPE",
        )

    @override_settings(
        AI_JSON_BODY_MAX_BYTES=50
    )
    def test_oversized_body_is_rejected(self):
        response = self.post(
            json.dumps(
                {
                    "message": "x" * 100
                }
            )
        )

        self.assertEqual(
            response.status_code,
            413,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "REQUEST_TOO_LARGE",
        )

    @override_settings(
        AI_CHAT_MAX_CHARS=10
    )
    def test_oversized_message_is_rejected(self):
        response = self.post(
            json.dumps(
                {
                    "message": "x" * 11
                }
            )
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "VALIDATION_ERROR",
        )

        self.assertEqual(
            ChatSession.objects.filter(
                user=self.user
            ).count(),
            0,
        )

    def test_unknown_session_returns_404(self):
        response = self.post(
            json.dumps(
                {
                    "message": "hello",
                    "session_id": 999999,
                }
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "SESSION_NOT_FOUND",
        )

        self.assertEqual(
            ChatSession.objects.filter(
                user=self.user
            ).count(),
            0,
        )

    @patch(
        "ai_tools.views.GeminiService",
        side_effect=RuntimeError(
            "SECRET_PROVIDER_DETAIL"
        ),
    )
    def test_provider_error_is_not_exposed(
        self,
        mocked_service,
    ):
        with self.assertLogs(
            "ai_tools.views",
            level="ERROR",
        ):
            response = self.post(
                json.dumps(
                    {
                        "message": "hello"
                    }
                )
            )

        self.assertEqual(
            response.status_code,
            500,
        )

        content = response.content.decode()

        self.assertNotIn(
            "SECRET_PROVIDER_DETAIL",
            content,
        )

        payload = json.loads(
            response.content
        )

        self.assertEqual(
            payload["error_code"],
            "INTERNAL_ERROR",
        )


import tempfile
from pathlib import Path
from django.core.files.uploadedfile import SimpleUploadedFile


@override_settings(
    AI_FEATURES_ENABLED=True,
    IMAGE_ANALYSIS_ENABLED=True,
    RATE_LIMIT_ENABLED=False,
)
class ImageAnalysisValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="image-validation-user",
            password="StrongPass123!",
        )

        self.client.force_login(self.user)

        self.url = reverse(
            "ai_tools:image_analyzer"
        )

        self.media_directory = (
            tempfile.TemporaryDirectory()
        )

        self.media_override = self.settings(
            MEDIA_ROOT=(
                self.media_directory.name
            )
        )

        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def upload(self):
        output = BytesIO()
        Image.new("RGB", (4, 4), "teal").save(
            output,
            format="PNG",
        )
        return SimpleUploadedFile(
            "sample.png",
            output.getvalue(),
            content_type="image/png",
        )

    def test_invalid_analysis_type_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "analysis_type": "executable",
                "image": self.upload(),
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json()["error_code"],
            "VALIDATION_ERROR",
        )

    @override_settings(
        AI_IMAGE_QUESTION_MAX_CHARS=5
    )
    def test_oversized_question_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "analysis_type": "general",
                "user_question": "x" * 6,
                "image": self.upload(),
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )



    def test_invalid_binary_file_is_rejected(self):
        upload = SimpleUploadedFile(
            "fake.png",
            b"this-is-not-an-image",
            content_type="image/png",
        )
        response = self.client.post(
            self.url,
            {"analysis_type": "general", "image": upload},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_IMAGE")

    @override_settings(AI_IMAGE_MAX_PIXELS=3)
    def test_pixel_limit_is_enforced(self):
        response = self.client.post(
            self.url,
            {"analysis_type": "general", "image": self.upload()},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_IMAGE")

    @patch(
        "ai_tools.views.GeminiService"
    )
    def test_failure_removes_record_and_file(
        self,
        service_class,
    ):
        service_class.return_value            .analyze_image            .return_value = {
                "success": False,
                "error": (
                    "SECRET_IMAGE_PROVIDER_DETAIL"
                ),
            }

        with self.assertLogs(
            "ai_tools.views",
            level="WARNING",
        ):
            response = self.client.post(
                self.url,
                {
                    "analysis_type": "general",
                    "image": self.upload(),
                },
            )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertNotIn(
            "SECRET_IMAGE_PROVIDER_DETAIL",
            response.content.decode(),
        )

        from .models import ImageAnalysis

        self.assertEqual(
            ImageAnalysis.objects.filter(
                user=self.user
            ).count(),
            0,
        )

        files = [
            path
            for path in Path(
                self.media_directory.name
            ).rglob("*")
            if path.is_file()
        ]

        self.assertEqual(files, [])


from io import BytesIO
from PIL import Image


class ChatSessionsPageTests(TestCase):
    def test_page_is_owner_scoped(self):
        owner = User.objects.create_user(
            username="chat-page-owner",
            password="StrongPass123!",
        )
        other = User.objects.create_user(
            username="chat-page-other",
            password="StrongPass123!",
        )
        ChatSession.objects.create(user=owner, title="Owner session")
        ChatSession.objects.create(user=other, title="Other session")
        self.client.force_login(owner)
        response = self.client.get(reverse("ai_tools:chat_sessions_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Owner session")
        self.assertNotContains(response, "Other session")
