"""Project-level operational endpoints."""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Return readiness only when the application can query its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {"status": "unhealthy", "database": "unavailable"},
            status=503,
        )
    return JsonResponse({"status": "healthy", "database": "ok"})
