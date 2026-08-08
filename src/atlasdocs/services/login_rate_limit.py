"""Simple in-process login rate limiter (per IP + username)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from atlasdocs.config import get_settings


class LoginRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _window(self) -> float:
        return float(get_settings().login_rate_limit_window_seconds)

    def _limit(self) -> int:
        return get_settings().login_rate_limit_attempts

    def _prune(self, key: str, now: float) -> None:
        window = self._window()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()

    def check(self, *, client_ip: str, username: str) -> bool:
        """Return True if the attempt is allowed."""
        now = time.monotonic()
        with self._lock:
            for key in (f"ip:{client_ip}", f"user:{username.strip().lower()}"):
                self._prune(key, now)
                if len(self._hits[key]) >= self._limit():
                    return False
            return True

    def record_failure(self, *, client_ip: str, username: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in (f"ip:{client_ip}", f"user:{username.strip().lower()}"):
                self._prune(key, now)
                self._hits[key].append(now)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


login_rate_limiter = LoginRateLimiter()
