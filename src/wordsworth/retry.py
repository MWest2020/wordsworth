"""Bounded retry for transient downstream failures (pipeline-resilience).

A transient failure of a downstream service (OpenAnonymiser, Ollama, OpenSearch)
must not abort a run — a short blip self-heals with backoff. Permanent/logic
errors are never retried; they raise immediately, so fail-hard is preserved and a
document that genuinely cannot be de-identified never reaches the index."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

import httpx

from .extraction import ExtractionError
from .profiling import ProfilingError

T = TypeVar("T")

# Logic/permanent errors — a retry cannot help, so never retry them.
_PERMANENT = (ExtractionError, ProfilingError, ValueError, TypeError, KeyError)


def is_transient(exc: BaseException) -> bool:
    """True for a downstream blip worth retrying (service unreachable / slow /
    5xx), False for a permanent or logic error. ``AnonymizationEngineError`` wraps
    a service-unreachable condition, so it is transient. HTTP/transport errors are
    matched across client libraries by duck-typing a status code and by the
    connection/timeout error names (httpx and opensearch-py alike)."""
    if isinstance(exc, _PERMANENT):
        return False
    from .openanonymiser_driver import AnonymizationEngineError
    if isinstance(exc, AnonymizationEngineError):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError, httpx.TransportError)):
        return True
    # Anything carrying an HTTP status: only 5xx is transient (4xx is a bug).
    status = getattr(exc, "status_code", None)
    if status is None:
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)
    if status is not None:
        try:
            return int(status) >= 500
        except (TypeError, ValueError):
            return False
    # opensearch-py connection/timeout errors carry no status code.
    name = type(exc).__name__.lower()
    return "connection" in name or "timeout" in name


def retry_transient(
    fn: Callable[[], T],
    attempts: int,
    base_delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn``, retrying ONLY transient errors up to ``attempts`` total tries
    with exponential backoff (``base_delay * 2**i``). Re-raises the last error when
    attempts are exhausted; a permanent error re-raises immediately without retry.
    ``sleep`` is injectable so tests do not actually wait."""
    attempts = max(1, attempts)
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if not is_transient(exc) or i == attempts - 1:
                raise
            sleep(base_delay * (2 ** i))
    raise AssertionError("unreachable")  # the loop always returns or raises
