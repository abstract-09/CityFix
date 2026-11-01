"""Tiny in-memory sliding-window limiter (per client IP). Fine for one process; use a shared store in production."""
import functools
import threading
import time
from collections import defaultdict, deque

from flask import current_app, request

from .errors import ApiError


class RateLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


def rate_limited(kind: str = "general"):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            c = current_app.extensions["cityfix"]
            limit = c.settings.login_rate_limit if kind == "login" else c.settings.rate_limit_per_minute
            if limit > 0 and not c.limiter.allow(f"{kind}:{request.remote_addr}", limit):
                raise ApiError(429, "Too many requests. Please wait a minute and try again")
            return fn(*args, **kwargs)
        return wrapper
    return decorator
