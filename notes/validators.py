"""Validation helpers for user-created bookmarks."""

from __future__ import annotations

from urllib.parse import urlsplit

from ai_tools.api import APIRequestError


def validate_bookmark_url(value):
    if any(character in value for character in "\r\n\x00"):
        raise APIRequestError("INVALID_BOOKMARK_URL", "The bookmark URL is invalid.", 400)

    if value.startswith("/") and not value.startswith("//"):
        return value

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise APIRequestError(
            "INVALID_BOOKMARK_URL",
            "Bookmarks must use http, https, or an internal relative path.",
            400,
        )

    return value
