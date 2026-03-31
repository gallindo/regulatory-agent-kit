"""Tests for token bucket rate limiter."""

import asyncio
import time

import pytest

from regulatory_agent_kit.tools.rate_limiter import (
    RateLimiterRegistry,
    TokenBucket,
)


class TestTokenBucket:
    """Tests for the TokenBucket rate limiter."""

    def test_initial_tokens_equal_burst(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=5)
        assert bucket.available_tokens == pytest.approx(5.0, abs=0.1)

    async def test_acquire_reduces_tokens(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=5)
        await bucket.acquire(1)
        assert bucket.available_tokens < 5.0

    async def test_acquire_multiple_tokens(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=10)
        await bucket.acquire(5)
        assert bucket.available_tokens == pytest.approx(5.0, abs=0.5)

    async def test_try_acquire_success(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=5)
        result = await bucket.try_acquire(1)
        assert result is True

    async def test_try_acquire_failure(self) -> None:
        bucket = TokenBucket(rate=0.1, burst=1)
        await bucket.acquire(1)
        result = await bucket.try_acquire(1)
        assert result is False

    async def test_acquire_waits_when_empty(self) -> None:
        bucket = TokenBucket(rate=100.0, burst=1)
        await bucket.acquire(1)  # Empty the bucket
        start = time.monotonic()
        await bucket.acquire(1)  # Should wait for refill
        elapsed = time.monotonic() - start
        assert elapsed >= 0.005  # Should have waited some time

    async def test_refill_over_time(self) -> None:
        bucket = TokenBucket(rate=1000.0, burst=10)
        await bucket.acquire(10)  # Empty
        await asyncio.sleep(0.01)  # Wait for refill
        assert bucket.available_tokens > 0

    async def test_tokens_capped_at_burst(self) -> None:
        bucket = TokenBucket(rate=1000.0, burst=5)
        await asyncio.sleep(0.1)  # Wait longer than needed
        assert bucket.available_tokens <= 5.0

    async def test_acquire_returns_wait_time(self) -> None:
        bucket = TokenBucket(rate=100.0, burst=1)
        waited = await bucket.acquire(1)
        assert waited == 0.0  # First acquire should not wait

    async def test_concurrent_acquires(self) -> None:
        bucket = TokenBucket(rate=100.0, burst=10)
        results = await asyncio.gather(*[bucket.acquire(1) for _ in range(5)])
        assert len(results) == 5


class TestRateLimiterRegistry:
    """Tests for the RateLimiterRegistry."""

    def test_get_limiter_creates_new(self) -> None:
        registry = RateLimiterRegistry(default_rate=5.0, default_burst=10)
        limiter = registry.get_limiter("model-a")
        assert limiter.rate == 5.0
        assert limiter.burst == 10

    def test_get_limiter_returns_same(self) -> None:
        registry = RateLimiterRegistry()
        limiter1 = registry.get_limiter("model-a")
        limiter2 = registry.get_limiter("model-a")
        assert limiter1 is limiter2

    def test_configure_custom_limiter(self) -> None:
        registry = RateLimiterRegistry()
        registry.configure("fast-model", rate=100.0, burst=50)
        limiter = registry.get_limiter("fast-model")
        assert limiter.rate == 100.0
        assert limiter.burst == 50

    async def test_acquire_through_registry(self) -> None:
        registry = RateLimiterRegistry(default_rate=10.0, default_burst=5)
        waited = await registry.acquire("model-a")
        assert waited == 0.0

    async def test_try_acquire_through_registry(self) -> None:
        registry = RateLimiterRegistry(default_rate=10.0, default_burst=5)
        result = await registry.try_acquire("model-a")
        assert result is True

    def test_keys_property(self) -> None:
        registry = RateLimiterRegistry()
        registry.get_limiter("a")
        registry.get_limiter("b")
        assert sorted(registry.keys) == ["a", "b"]

    def test_default_values(self) -> None:
        registry = RateLimiterRegistry()
        assert registry.default_rate == 10.0
        assert registry.default_burst == 20
