"""Redis-backed result cache for resolved views.

FalkorDB runs on Redis, so a view's resolved table can be cached in the very same
instance under a key derived from the graph, view name and filters, with the view's
``ttl_seconds`` as the expiry. The graph and the cache share one connection — on a
FalkorDB graph handle the underlying ``redis.Redis`` client is reachable as
``graph.client.connection``. When it cannot be reached the cache is simply skipped, so
resolution still works (just always live).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_PREFIX = "doop:viewcache"


def redis_from_graph(graph: Any) -> Any:
    """Best-effort: reach the underlying redis client of a FalkorDB graph handle.
    Returns ``None`` if it cannot be located (caching is then skipped)."""
    client = getattr(graph, "client", None)
    return getattr(client, "connection", None)


def view_cache_key(graph_name: str, view_name: str, filters: dict[str, Any]) -> str:
    """Stable key for a (graph, view, filters) triple. Filters are hashed so the key
    length stays bounded regardless of filter payload."""
    digest = hashlib.sha1(
        json.dumps(filters or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()
    return f"{_PREFIX}:{graph_name}:{view_name}:{digest}"


def cache_get(redis: Any, key: str) -> Any:
    """Return the cached value for ``key`` (decoded JSON) or ``None`` on miss/error."""
    if redis is None:
        return None
    raw = redis.get(key)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def cache_set(redis: Any, key: str, value: Any, ttl_seconds: int | None) -> None:
    """Store ``value`` (JSON-encoded) under ``key`` with a TTL. No-op without a positive
    TTL or a usable redis client."""
    if redis is None or not ttl_seconds or ttl_seconds <= 0:
        return
    redis.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False, default=str))
