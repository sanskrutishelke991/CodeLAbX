"""Django filters for sanitized AI-generated content."""

from django import template
from django.utils.safestring import mark_safe

from ai_tools.rendering import sanitize_ai_html

register = template.Library()


@register.filter(name="safe_ai_html")
def safe_ai_html(value):
    """Sanitize an AI fragment before rendering HTML."""
    return mark_safe(
        sanitize_ai_html(value)
    )
