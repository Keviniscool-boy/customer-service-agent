from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class LoginRateLimiter:
    """单进程登录失败限流，适合本地和单实例部署。"""

    def __init__(self, max_failures: int = 5, window_seconds: int = 60):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures = defaultdict(deque)
        self._lock = Lock()

    def _remove_expired(self, key: str, now: float) -> deque:
        attempts = self._failures[key]
        while attempts and now - attempts[0] >= self.window_seconds:
            attempts.popleft()
        return attempts

    def is_blocked(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            attempts = self._remove_expired(key, now)
            if not attempts:
                self._failures.pop(key, None)
            return len(attempts) >= self.max_failures

    def record_failure(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            attempts = self._remove_expired(key, now)
            attempts.append(now)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def retry_after(self, key: str) -> int:
        now = monotonic()
        with self._lock:
            attempts = self._remove_expired(key, now)
            if not attempts:
                self._failures.pop(key, None)
                return 0
            return max(1, int(self.window_seconds - (now - attempts[0])))
