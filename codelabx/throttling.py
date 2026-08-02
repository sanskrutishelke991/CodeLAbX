"""Small cache-backed throttles for authentication endpoints."""

from __future__ import annotations

import hashlib

from django.core.cache import cache


def _client_key(request):
    address = request.META.get("REMOTE_ADDR", "unknown")
    return hashlib.sha256(address.encode("utf-8")).hexdigest()[:20]


def is_rate_limited(request, scope, limit, window):
    key = f"web-rate:{scope}:{_client_key(request)}"
    if cache.add(key, 1, timeout=window):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        count = 1
    return count > limit
