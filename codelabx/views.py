"""Project-level liveness and readiness endpoints."""

from __future__ import annotations

import secrets
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def _no_store(response: JsonResponse) -> JsonResponse:
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def live(request):
    """Report that the Django process can serve requests."""
    return _no_store(JsonResponse({"status": "alive"}))


@require_GET
def health(request):
    """Report readiness only when the database and cache are usable."""
    components = {
        "database": "ok",
        "cache": "ok",
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        components["database"] = "unavailable"

    token = secrets.token_urlsafe(12)
    cache_key = f"readiness:{token}"
    try:
        cache.set(cache_key, token, timeout=5)
        if cache.get(cache_key) != token:
            components["cache"] = "unavailable"
    except Exception:
        components["cache"] = "unavailable"
    finally:
        try:
            cache.delete(cache_key)
        except Exception:
            pass

    ready = all(value == "ok" for value in components.values())
    payload = {
        "status": "healthy" if ready else "unhealthy",
        **components,
    }
    return _no_store(
        JsonResponse(payload, status=200 if ready else 503)
    )


@require_GET
def service_worker(request):
    """Serve the versioned worker at root scope without caching user pages."""
    worker_path = Path(settings.BASE_DIR) / "static" / "js" / "service-worker.js"
    response = HttpResponse(
        worker_path.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    """Render a generic cache-safe offline fallback with no account data."""
    response = render(request, "pwa/offline.html")
    response["Cache-Control"] = "public, max-age=300"
    return response
