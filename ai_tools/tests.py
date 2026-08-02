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
