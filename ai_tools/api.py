"""Validation and safe error helpers for JSON APIs."""

from __future__ import annotations

import json
import logging
from functools import wraps

from django.conf import settings
from django.http import Http404, JsonResponse


class APIRequestError(Exception):
    def __init__(
        self,
        code,
        message,
        status=400,
    ):
        super().__init__(message)

        self.code = code
        self.message = message
        self.status = status

    def response(self):
        return json_error(
            self.code,
            self.message,
            self.status,
        )


def json_error(
    code,
    message,
    status,
):
    return JsonResponse(
        {
            "success": False,
            "error": message,
            "error_code": code,
        },
        status=status,
    )


def parse_json_object(
    request,
    max_bytes=None,
):
    limit = (
        max_bytes
        or settings.AI_JSON_BODY_MAX_BYTES
    )

    content_length = request.META.get(
        "CONTENT_LENGTH"
    )

    if content_length:
        try:
            if int(content_length) > limit:
                raise APIRequestError(
                    "REQUEST_TOO_LARGE",
                    "The request body is too large.",
                    413,
                )
        except ValueError as exc:
            raise APIRequestError(
                "INVALID_CONTENT_LENGTH",
                "The request metadata is invalid.",
                400,
            ) from exc

    if request.content_type != "application/json":
        raise APIRequestError(
            "UNSUPPORTED_MEDIA_TYPE",
            (
                "Content-Type must be "
                "application/json."
            ),
            415,
        )

    body = request.body

    if len(body) > limit:
        raise APIRequestError(
            "REQUEST_TOO_LARGE",
            "The request body is too large.",
            413,
        )

    try:
        data = json.loads(body)
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        raise APIRequestError(
            "INVALID_JSON",
            (
                "The request body must contain "
                "valid JSON."
            ),
            400,
        ) from exc

    if not isinstance(data, dict):
        raise APIRequestError(
            "INVALID_JSON_OBJECT",
            "The JSON body must be an object.",
            400,
        )

    return data


def text_field(
    data,
    name,
    *,
    default=None,
    required=False,
    min_length=0,
    max_length,
):
    if (
        name not in data
        or data[name] is None
    ):
        if required:
            raise APIRequestError(
                "VALIDATION_ERROR",
                f"{name} is required.",
            )

        return default

    value = data[name]

    if not isinstance(value, str):
        raise APIRequestError(
            "VALIDATION_ERROR",
            f"{name} must be text.",
        )

    value = value.strip()

    if required and not value:
        raise APIRequestError(
            "VALIDATION_ERROR",
            f"{name} cannot be empty.",
        )

    if len(value) < min_length:
        raise APIRequestError(
            "VALIDATION_ERROR",
            f"{name} is too short.",
        )

    if len(value) > max_length:
        raise APIRequestError(
            "VALIDATION_ERROR",
            f"{name} is too long.",
        )

    return value


def integer_field(
    data,
    name,
    *,
    default=None,
    required=False,
    minimum=None,
    maximum=None,
):
    if (
        name not in data
        or data[name] is None
    ):
        if required:
            raise APIRequestError(
                "VALIDATION_ERROR",
                f"{name} is required.",
            )

        return default

    value = data[name]

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise APIRequestError(
            "VALIDATION_ERROR",
            f"{name} must be an integer.",
        )

    if (
        minimum is not None
        and value < minimum
    ):
        raise APIRequestError(
            "VALIDATION_ERROR",
            (
                f"{name} is below "
                "the allowed minimum."
            ),
        )

    if (
        maximum is not None
        and value > maximum
    ):
        raise APIRequestError(
            "VALIDATION_ERROR",
            (
                f"{name} is above "
                "the allowed maximum."
            ),
        )

    return value


def choice_field(
    data,
    name,
    *,
    choices,
    default=None,
    required=False,
):
    value = text_field(
        data,
        name,
        default=default,
        required=required,
        max_length=100,
    )

    if value not in choices:
        raise APIRequestError(
            "VALIDATION_ERROR",
            (
                f"{name} contains "
                "an unsupported value."
            ),
        )

    return value


def provider_error_response(
    logger,
    operation,
    detail=None,
):
    logger.warning(
        "AI provider failure during %s: %s",
        operation,
        detail or "unknown",
    )

    return json_error(
        "AI_SERVICE_ERROR",
        (
            "The AI service could not complete "
            "this request. Please try again later."
        ),
        502,
    )


def safe_api_errors(view):
    logger = logging.getLogger(
        view.__module__
    )

    @wraps(view)
    def wrapped(
        request,
        *args,
        **kwargs,
    ):
        try:
            return view(
                request,
                *args,
                **kwargs,
            )
        except APIRequestError as exc:
            return exc.response()
        except Http404:
            raise
        except Exception:
            logger.exception(
                "Unhandled API error in %s",
                view.__name__,
            )

            return json_error(
                "INTERNAL_ERROR",
                (
                    "An unexpected error occurred. "
                    "Please try again later."
                ),
                500,
            )

    return wrapped
