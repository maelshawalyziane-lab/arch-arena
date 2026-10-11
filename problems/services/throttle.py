"""
Fixed-window rate limiting for the expensive verification endpoint.

Every `/api/problems/<id>/verify` call may cost a few cents of LLM budget, so the
endpoint is throttled per user (and per remote address for anonymous traffic).
The counter lives in the Django cache; swap the cache backend for Redis/Memcached
in production so the limit is shared by every worker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from django.core.cache import cache


@dataclass
class ThrottleResult:
    allowed: bool
    remaining: int
    retry_after: int  # seconds until the window resets

    @property
    def reset_seconds(self) -> int:
        return max(self.retry_after, 0)


def hit(*, identity: str, limit: int, window_seconds: int, namespace: str = "verify") -> ThrottleResult:
    """
    Register one attempt for ``identity`` and report whether it is allowed.

    ``limit <= 0`` disables throttling (used by tests and by "trusted" deployments).
    """
    if limit <= 0:
        return ThrottleResult(allowed=True, remaining=10**9, retry_after=0)

    key = f"{namespace}:{identity}"
    now = time.time()
    state = cache.get(key)
    if not isinstance(state, dict) or state.get("reset", 0) <= now:
        state = {"count": 0, "reset": now + window_seconds}

    state["count"] += 1
    ttl = max(1, int(state["reset"] - now))
    cache.set(key, state, timeout=ttl)

    remaining = max(0, limit - state["count"])
    return ThrottleResult(allowed=state["count"] <= limit, remaining=remaining, retry_after=ttl)


def peek(*, identity: str, limit: int, namespace: str = "verify") -> int:
    """Remaining attempts without consuming one (used by the dashboard/API status)."""
    state = cache.get(f"{namespace}:{identity}") or {}
    return max(0, limit - int(state.get("count", 0))) if limit > 0 else 10**9
