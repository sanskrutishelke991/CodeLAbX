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
