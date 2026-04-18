"""In-process sliding-window rate limiter.

Keyed on (route_family, identifier). Single-instance deployment only — see
AccountManagementSpec §8.3. Not safe across multiple uvicorn workers; v1
assumes a single worker and single instance.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Final


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_tick(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Return True if this tick is allowed, False if over the limit."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._windows[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()


# Shared process-wide limiter for routes/auth.py and routes/admin.py.
LIMITS: Final[dict[str, tuple[int, int]]] = {
    "login_ip": (20, 5 * 60),
    "login_email": (10, 5 * 60),
    "password_reset_ip": (5, 60 * 60),
    "register_ip": (5, 60 * 60),
}


_limiter = SlidingWindowLimiter()


def limiter() -> SlidingWindowLimiter:
    return _limiter
