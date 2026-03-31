"""Token bucket rate limiter for LLM API calls."""

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Async token bucket rate limiter.

    Controls the rate of operations using the token bucket algorithm.
    Tokens are added at a fixed rate up to a maximum burst size.
    Each operation consumes one or more tokens.
    """

    rate: float
    burst: int
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize mutable state after dataclass init."""
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            Time spent waiting in seconds.
        """
        waited = 0.0
        async with self._lock:
            self._refill()
            while self._tokens < tokens:
                deficit = tokens - self._tokens
                wait_time = deficit / self.rate
                await asyncio.sleep(wait_time)
                waited += wait_time
                self._refill()
            self._tokens -= tokens
        return waited

    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Returns:
            True if tokens were acquired, False otherwise.
        """
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        self._refill()
        return self._tokens


@dataclass
class RateLimiterRegistry:
    """Registry of rate limiters keyed by model or endpoint."""

    default_rate: float = 10.0
    default_burst: int = 20
    _limiters: dict[str, TokenBucket] = field(init=False, default_factory=dict)

    def get_limiter(self, key: str) -> TokenBucket:
        """Get or create a rate limiter for the given key."""
        if key not in self._limiters:
            self._limiters[key] = TokenBucket(
                rate=self.default_rate,
                burst=self.default_burst,
            )
        return self._limiters[key]

    def configure(self, key: str, rate: float, burst: int) -> None:
        """Configure a rate limiter for a specific key."""
        self._limiters[key] = TokenBucket(rate=rate, burst=burst)

    async def acquire(self, key: str, tokens: int = 1) -> float:
        """Acquire tokens from the limiter for the given key."""
        limiter = self.get_limiter(key)
        return await limiter.acquire(tokens)

    async def try_acquire(self, key: str, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        limiter = self.get_limiter(key)
        return await limiter.try_acquire(tokens)

    @property
    def keys(self) -> list[str]:
        """Return all registered limiter keys."""
        return list(self._limiters.keys())
