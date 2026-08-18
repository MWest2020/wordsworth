"""Bounded concurrency limiter (ADR-0001) + DB pool sizing."""
from __future__ import annotations

import threading
import time

from wordsworth.concurrency import limiter
from wordsworth.db import make_engine

# A Postgres URL builds a QueuePool without connecting (pool args apply); sqlite
# would use SingletonThreadPool, which rejects pool_size/max_overflow.
_PG_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def test_limiter_bounds_concurrent_entries():
    size = 2
    active = 0
    peak = 0
    lock = threading.Lock()
    barrier_done = threading.Event()

    def worker():
        nonlocal active, peak
        with limiter("test-bound", size):
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    barrier_done.set()
    assert peak <= size          # never more than the limit ran at once
    assert peak >= 1


def test_limiter_same_name_same_semaphore():
    assert limiter("dup", 3) is limiter("dup", 99)  # created once, size fixed


def test_make_engine_applies_configured_pool(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_DB_POOL_SIZE", "7")
    monkeypatch.setenv("WORDSWORTH_DB_MAX_OVERFLOW", "13")
    eng = make_engine(_PG_URL)           # builds without connecting
    assert eng.pool.size() == 7          # configured pool_size (not default 5)
    assert eng.pool._max_overflow == 13
