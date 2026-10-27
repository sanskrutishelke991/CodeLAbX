"""Safe rendering helpers for all AI-generated content."""

from __future__ import annotations

import markdown
import nh3

ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "code": {"class"},
    "th": {"align"},
    "td": {"align"},
}

ALLOWED_URL_SCHEMES = {
    "http",
    "https",
    "mailto",
}

CLEAN_CONTENT_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "svg",
    "math",
}


def sanitize_ai_html(value: str | None) -> str:
    """Sanitize HTML using an educational-content allowlist."""
    if not value:
        return ""

    return nh3.clean(
        str(value),
        tags=ALLOWED_TAGS,
        clean_content_tags=CLEAN_CONTENT_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        strip_comments=True,
        link_rel="noopener noreferrer",
    )


def render_ai_markdown(value: str | None) -> str:
    """Convert AI Markdown to sanitized HTML."""
    if not value:
        return ""

    rendered = markdown.markdown(
        str(value),
        extensions=[
            "fenced_code",
            "tables",
            "nl2br",
        ],
    )

    return sanitize_ai_html(rendered)
