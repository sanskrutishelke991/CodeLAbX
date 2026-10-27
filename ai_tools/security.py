"""Feature switches and request limits for AI endpoints."""

from __future__ import annotations

import hashlib
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone


class RequestGuardError(Exception):
    def __init__(
        self,
        code,
        message,
        status,
        retry_after=None,
    ):
        super().__init__(message)

        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after

    def response(self):
        response = JsonResponse(
            {
                "success": False,
                "error": self.message,
                "error_code": self.code,
            },
            status=self.status,
        )

        if self.retry_after is not None:
            response["Retry-After"] = str(
                self.retry_after
            )

        return response


def _subject(request):
    user = getattr(
        request,
        "user",
        None,
    )

    if (
        user is not None
        and getattr(
            user,
            "is_authenticated",
            False,
        )
    ):
        return f"user-{user.pk}"

    remote_address = request.META.get(
        "REMOTE_ADDR",
        "unknown",
    )

    digest = hashlib.sha256(
        remote_address.encode("utf-8")
    ).hexdigest()[:20]

    return f"ip-{digest}"


def _increment(key, timeout):
    if cache.add(
        key,
        1,
        timeout=timeout,
    ):
        return 1

    try:
        return cache.incr(key)
    except ValueError:
        cache.set(
            key,
            1,
            timeout=timeout,
        )

        return 1


def enforce_ai_limits(
    request,
    scope,
    burst_limit,
    feature_flag="AI_FEATURES_ENABLED",
):
    if not getattr(
        settings,
        feature_flag,
        False,
    ):
        raise RequestGuardError(
            "FEATURE_DISABLED",
            "This feature is currently unavailable.",
            503,
        )

    if not settings.RATE_LIMIT_ENABLED:
        return

    subject = _subject(request)

    window = (
        settings.AI_RATE_LIMIT_WINDOW_SECONDS
    )

    burst_key = (
        f"ai-rate:{scope}:{subject}"
    )

    burst_count = _increment(
        burst_key,
        window,
    )

    if burst_count > burst_limit:
        raise RequestGuardError(
            "RATE_LIMITED",
            (
                "Too many requests. "
                "Please wait before trying again."
            ),
            429,
            retry_after=window,
        )

    day = timezone.localdate().isoformat()

    daily_key = (
        f"ai-daily:{day}:{subject}"
    )

    daily_count = _increment(
        daily_key,
        26 * 60 * 60,
    )

    if (
        daily_count
        > settings.AI_DAILY_REQUEST_LIMIT
    ):
        raise RequestGuardError(
            "DAILY_AI_LIMIT_REACHED",
            (
                "Your daily AI request limit "
                "has been reached."
            ),
            429,
            retry_after=60 * 60,
        )


def guard_ai_request(
    request,
    scope,
    limit_setting,
    feature_flag="AI_FEATURES_ENABLED",
):
    try:
        enforce_ai_limits(
            request,
            scope,
            getattr(
                settings,
                limit_setting,
            ),
            feature_flag=feature_flag,
        )
    except RequestGuardError as exc:
        return exc.response()

    return None


def protect_ai_endpoint(
    scope,
    limit_setting,
    feature_flag="AI_FEATURES_ENABLED",
):
    def decorator(view):
        @wraps(view)
        def wrapped(
            request,
            *args,
            **kwargs,
        ):
            blocked = guard_ai_request(
                request,
                scope,
                limit_setting,
                feature_flag=feature_flag,
            )

            if blocked is not None:
                return blocked

            return view(
                request,
                *args,
                **kwargs,
            )

        return wrapped

    return decorator
