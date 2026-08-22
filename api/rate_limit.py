from collections import defaultdict, deque
import hashlib
import logging
from threading import Lock
from time import monotonic, time, time_ns

try:
    from redis import Redis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - only used without optional dependency
    Redis = None

    class RedisError(Exception):
        pass


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


class RedisLoginRateLimiter:
    """用 Redis 在多个后端进程之间共享登录失败限流。"""

    def __init__(
        self,
        redis_url: str,
        max_failures: int = 5,
        window_seconds: int = 60,
        timeout: float = 1.0,
    ):
        if Redis is None:
            raise RuntimeError("没有安装 redis 依赖")
        self.redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        self.max_failures = max_failures
        self.window_seconds = window_seconds

    @staticmethod
    def _key(key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"ecom-agent:login-failures:{digest}"

    def _remove_expired(self, redis_key: str, now: float) -> None:
        self.redis.zremrangebyscore(
            redis_key,
            "-inf",
            now - self.window_seconds,
        )

    def is_blocked(self, key: str) -> bool:
        now = time()
        redis_key = self._key(key)
        self._remove_expired(redis_key, now)
        return self.redis.zcard(redis_key) >= self.max_failures

    def record_failure(self, key: str) -> None:
        now = time()
        redis_key = self._key(key)
        member = f"{now}:{now_ns()}"
        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(redis_key, "-inf", now - self.window_seconds)
        pipeline.zadd(redis_key, {member: now})
        pipeline.expire(redis_key, self.window_seconds)
        pipeline.execute()

    def record_success(self, key: str) -> None:
        self.redis.delete(self._key(key))

    def retry_after(self, key: str) -> int:
        redis_key = self._key(key)
        now = time()
        self._remove_expired(redis_key, now)
        attempts = self.redis.zrange(redis_key, 0, 0, withscores=True)
        if not attempts:
            return 0
        return max(1, int(self.window_seconds - (now - attempts[0][1])))


def now_ns() -> int:
    """为同一秒内的多次失败生成不重复的 Redis 成员值。"""

    return time_ns()


class ResilientLoginRateLimiter:
    """Redis 不可用时回退到本地限流，避免登录接口整体失效。"""

    def __init__(self, primary, fallback: LoginRateLimiter | None = None):
        self.primary = primary
        self.fallback = fallback or LoginRateLimiter(
            max_failures=primary.max_failures,
            window_seconds=primary.window_seconds,
        )
        self._fallback_active = False
        self.logger = logging.getLogger(__name__)

    def _call(self, method: str, *args):
        if self._fallback_active:
            return getattr(self.fallback, method)(*args)
        try:
            return getattr(self.primary, method)(*args)
        except RedisError:
            self._fallback_active = True
            self.logger.warning("Redis 限流不可用，已回退本地内存限流")
            return getattr(self.fallback, method)(*args)

    def is_blocked(self, key: str) -> bool:
        return self._call("is_blocked", key)

    def record_failure(self, key: str) -> None:
        self._call("record_failure", key)

    def record_success(self, key: str) -> None:
        self._call("record_success", key)

    def retry_after(self, key: str) -> int:
        return self._call("retry_after", key)


def create_login_rate_limiter(
    redis_url: str,
    redis_timeout_seconds: float = 1.0,
):
    """根据环境变量选择 Redis 限流或本地限流。"""

    if not redis_url.strip():
        return LoginRateLimiter()
    return ResilientLoginRateLimiter(
        RedisLoginRateLimiter(
            redis_url,
            timeout=redis_timeout_seconds,
        )
    )
