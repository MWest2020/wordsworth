# SPDX-License-Identifier: MIT
"""Two requests pseudonymising the same value at the same time.

Two threads in one pod or two replicas, it is the same race: both read
"absent", both insert, and the loser used to fail its whole ingest on the
primary key. Since #465 a `put` is buffered and written under the audit chain
lock (`write_pending`), so the second writer waits for that lock, not for the
first one's uncommitted row; the first row still wins. Both write the way
every caller must: nothing writes a buffered row at commit any more.
"""
import threading

from sqlalchemy import func, select

from race_setup import wait_for_a_lock_waiter
from wordsworth.mapping_buffer import write_pending
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import PiiMapping


def test_an_overlapping_insert_of_the_same_pseudonym_does_not_fail(session_factory):
    errors = []
    first = session_factory()
    PostgresMappingStore(first).put("PERSON_abc", b"ct1", b"n" * 12, "k1")
    write_pending(first)  # stored, not committed; the chain lock is held

    def second():
        try:
            with session_factory() as s:
                PostgresMappingStore(s).put("PERSON_abc", b"ct2", b"m" * 12, "k1")
                write_pending(s)  # waits for the chain lock, then finds the row
                s.commit()
        except Exception as exc:   # noqa: BLE001 -- the failure is the finding
            errors.append(exc)

    t = threading.Thread(target=second)
    t.start()
    wait_for_a_lock_waiter(session_factory)  # the second waits for the chain lock
    first.commit()
    first.close()
    t.join(10)

    assert errors == []
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(PiiMapping)) == 1
        assert s.get(PiiMapping, "PERSON_abc").ciphertext == b"ct1"
