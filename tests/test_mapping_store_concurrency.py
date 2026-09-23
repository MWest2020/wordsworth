# SPDX-License-Identifier: MIT
"""Two requests pseudonymising the same value at the same time.

Two threads in one pod or two replicas, it is the same race: both read
"absent", both insert, and the loser used to fail its whole ingest on the
primary key.
"""
import threading
import time

from sqlalchemy import func, select

from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import PiiMapping


def test_an_overlapping_insert_of_the_same_pseudonym_does_not_fail(session_factory):
    errors = []
    first = session_factory()
    PostgresMappingStore(first).put("PERSON_abc", b"ct1", b"n" * 12, "k1")

    def second():
        try:
            with session_factory() as s:
                PostgresMappingStore(s).put("PERSON_abc", b"ct2", b"m" * 12, "k1")
                s.commit()
        except Exception as exc:   # noqa: BLE001 -- the failure is the finding
            errors.append(exc)

    t = threading.Thread(target=second)
    t.start()
    time.sleep(0.5)          # the second insert is now waiting on the first
    first.commit()
    first.close()
    t.join(10)

    assert errors == []
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(PiiMapping)) == 1
        assert s.get(PiiMapping, "PERSON_abc").ciphertext == b"ct1"
