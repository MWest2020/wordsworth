"""Per-client API rate limiting: a token-bucket behind a swappable store.

Boring on purpose, no new dependency. A bucket refills at `rate` tokens/sec up
to `burst` capacity; each request costs one token; an empty bucket is rejected
with the whole seconds until the next token frees (the Retry-After hint). The
monotonic clock is injectable so refill is testable without sleeping.

The per-key state lives behind `RateLimitStore` (in-memory default) so a shared
backend (e.g. Redis) can replace it for multi-instance deployments later, behind
the same interface. No silent fallback: a bad config is a hard error at build."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Monitoring must never be throttled (design decision).
EXEMPT_PATHS = frozenset({"/health", "/metrics"})


@dataclass(frozen=True)
class BucketState:
    """Snapshot of one client's bucket: current tokens and when they were set."""

    tokens: float
    updated_at: float


class RateLimitStore(Protocol):
    """Per-key token-bucket state. Swappable for a shared backend later."""

    def get(self, key: str) -> BucketState | None: ...

    def put(self, key: str, state: BucketState) -> None: ...


class InMemoryStore:
    """Default single-instance store. A plain dict, no eviction (PoC scope)."""

    def __init__(self) -> None:
        self._buckets: dict[str, BucketState] = {}

    def get(self, key: str) -> BucketState | None:
        return self._buckets.get(key)

    def put(self, key: str, state: BucketState) -> None:
        self._buckets[key] = state


@dataclass(frozen=True)
class Decision:
    """Outcome of a check. `retry_after` is whole seconds, 0 when allowed."""

    allowed: bool
    retry_after: int


class TokenBucket:
    """Token-bucket limiter: `rate` tokens/sec, capacity `burst`."""

    def __init__(
        self,
        rate: float,
        burst: float,
        store: RateLimitStore | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate <= 0 or burst <= 0:
            raise ValueError("rate and burst must be positive")
        self._rate = rate
        self._burst = burst
        self._store = store if store is not None else InMemoryStore()
        self._clock = clock

    def check(self, key: str) -> Decision:
        now = self._clock()
        state = self._store.get(key)
        if state is None:
            tokens = float(self._burst)
        else:
            elapsed = max(0.0, now - state.updated_at)
            tokens = min(self._burst, state.tokens + elapsed * self._rate)
        if tokens >= 1.0:
            self._store.put(key, BucketState(tokens - 1.0, now))
            return Decision(allowed=True, retry_after=0)
        # Keep the accrued fraction so continued waiting still refills correctly.
        self._store.put(key, BucketState(tokens, now))
        retry_after = max(1, math.ceil((1.0 - tokens) / self._rate))
        return Decision(allowed=False, retry_after=retry_after)


def client_key(request: Request) -> str:
    """Identify the client: API key if present, else source IP."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


class RateLimitMiddleware:
    """ASGI middleware. Limits the paths in `limiters`, exempts `exempt`."""

    def __init__(
        self,
        app: ASGIApp,
        limiters: Mapping[str, TokenBucket],
        exempt: frozenset[str],
    ) -> None:
        self.app = app
        self.limiters = dict(limiters)
        self.exempt = exempt

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        limiter = None if path in self.exempt else self.limiters.get(path)
        if limiter is not None:
            decision = limiter.check(client_key(Request(scope, receive)))
            if not decision.allowed:
                response = JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": str(decision.retry_after)},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def limiters_from_settings(
    settings,
    store_factory: Callable[[], RateLimitStore] = InMemoryStore,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, TokenBucket]:
    """Build the per-endpoint limiters from settings (one store per endpoint).

    Returns an empty mapping when disabled, so the middleware is simply omitted.
    The CPU-heavy `/ask` gets its own tighter bucket."""
    if not settings.rate_limit_enabled:
        return {}
    rate, burst = settings.rate_limit_rate, settings.rate_limit_burst
    ask_rate, ask_burst = settings.rate_limit_ask_rate, settings.rate_limit_ask_burst
    return {
        "/search": TokenBucket(rate, burst, store_factory(), clock),
        "/hybrid": TokenBucket(rate, burst, store_factory(), clock),
        "/ask": TokenBucket(ask_rate, ask_burst, store_factory(), clock),
    }
