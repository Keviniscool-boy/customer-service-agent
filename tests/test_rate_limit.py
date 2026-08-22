import unittest
from unittest.mock import Mock, patch

from redis.exceptions import RedisError

from api.rate_limit import (
    RedisRequestRateLimiter,
    RequestRateLimiter,
    ResilientLoginRateLimiter,
)


class RequestRateLimiterTest(unittest.TestCase):
    def test_request_limit_is_consumed_atomically(self):
        limiter = RequestRateLimiter(max_requests=2, window_seconds=60)

        self.assertEqual(limiter.consume("user-1"), (True, 0))
        self.assertEqual(limiter.consume("user-1"), (True, 0))
        allowed, retry_after = limiter.consume("user-1")

        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)

    def test_request_limiter_removes_expired_keys(self):
        limiter = RequestRateLimiter(max_requests=2, window_seconds=60)

        with patch("api.rate_limit.monotonic", side_effect=[0, 120]):
            limiter.consume("expired-user")
            limiter.consume("current-user")

        self.assertNotIn("expired-user", limiter._requests)
        self.assertIn("current-user", limiter._requests)

    def test_redis_login_limiter_retries_primary_after_cooldown(self):
        primary = Mock(max_failures=5, window_seconds=60)
        primary.is_blocked.side_effect = [RedisError("offline"), False]
        fallback = Mock()
        fallback.is_blocked.return_value = False
        limiter = ResilientLoginRateLimiter(primary, fallback)
        limiter.fallback_retry_seconds = 5

        with patch("api.rate_limit.monotonic", side_effect=[100, 102, 106]):
            self.assertFalse(limiter.is_blocked("user-1"))
            self.assertFalse(limiter.is_blocked("user-1"))
            self.assertFalse(limiter.is_blocked("user-1"))

        self.assertEqual(primary.is_blocked.call_count, 2)
        self.assertEqual(fallback.is_blocked.call_count, 2)

    def test_redis_request_limit_parses_string_result(self):
        with patch("api.rate_limit.Redis.from_url") as from_url:
            from_url.return_value.eval.return_value = ["0", "7"]
            limiter = RedisRequestRateLimiter(
                "redis://test",
                "chat",
                max_requests=1,
                window_seconds=60,
            )

            self.assertEqual(limiter.consume("user-1"), (False, 7))


if __name__ == "__main__":
    unittest.main()
