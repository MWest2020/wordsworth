"""Process-wide bounded concurrency for the memory-heavy backends (ADR-0001).

`/ingest` calls single-replica, CPU/memory-heavy backends (OpenAnonymiser GLiNER,
Ollama). Nothing bounded how many calls were in flight, so concurrent callers
could overwhelm them. These named semaphores cap concurrency per worker process;
acquire one as a context manager around the backend network call.

The limit is per process (per gunicorn worker). A cluster-wide total across
workers/replicas is a NiFi-layer / distributed-limiter concern (see ADR-0001),
out of scope here.
"""
from __future__ import annotations

import threading

_sems: dict[str, threading.BoundedSemaphore] = {}
_lock = threading.Lock()


def limiter(name: str, size: int) -> threading.BoundedSemaphore:
    """Return the process-wide bounded semaphore for ``name`` (created once).

    ``size`` is read on first use for a given name; use it as a context manager:
    ``with limiter("anonymize", n): ...``."""
    sem = _sems.get(name)
    if sem is None:
        with _lock:
            sem = _sems.get(name)
            if sem is None:
                sem = threading.BoundedSemaphore(max(1, size))
                _sems[name] = sem
    return sem
