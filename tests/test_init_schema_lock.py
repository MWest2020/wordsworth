# SPDX-License-Identifier: MIT
"""De uitrol overleeft een lezer die zijn transactie lang openhoudt.

Op 2026-09-18 liep de uitrol vast: een herstel-Job hield een leestransactie
tien minuten achter elkaar open, `init_schema` gaf na 5 seconden op, en de zes
pogingen van de Kubernetes-Job pasten allemaal in diezelfde tien minuten. De
docstring beweerde toen dat "een retry die een seconde later begint het slot
meestal vrij vindt" -- dat was een geruststelling zonder meting.

DB-gebonden, want dit gaat juist over echte Postgres-sloten: draait in CI en
lokaal met een database, skipt zonder.
"""
from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from wordsworth.db import init_schema, make_engine


def _lezer(engine, seconden: float, bezet: threading.Event):
    """Houdt ACCESS SHARE op `documents` vast -- precies wat een gewone lezer
    doet en wat een ALTER TABLE tegenhoudt."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1 FROM documents LIMIT 1"))
        bezet.set()
        time.sleep(seconden)
        conn.rollback()


def _heeft_kolom(engine, tabel: str, kolom: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :k"), {"t": tabel, "k": kolom}
        ).scalar() is not None


def _weg_ermee(engine, tabel: str, kolom: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {tabel} DROP COLUMN IF EXISTS {kolom}"))


def test_one_attempt_gives_up_while_a_reader_holds_the_table(session_factory,
                                                             database_url):
    """Zonder de wachtlus is dit wat er in productie gebeurde: de kolom die de
    migratie hoort terug te zetten blijft weg."""
    engine = make_engine(database_url)
    _weg_ermee(engine, "documents", "filename")
    bezet = threading.Event()
    t = threading.Thread(target=_lezer, args=(engine, 2.0, bezet))
    t.start()
    try:
        bezet.wait(5)
        with pytest.raises(OperationalError):
            init_schema(engine, attempts=1, lock_timeout="200ms")
        assert not _heeft_kolom(engine, "documents", "filename")
    finally:
        t.join()
        init_schema(engine)          # de volgende test begint heel


def test_it_waits_the_reader_out(session_factory, database_url):
    """Dezelfde lezer, dezelfde korte lock_timeout -- maar nu wacht init tot het
    slot vrijkomt en dóet hij de migratie alsnog.

    De assertie kijkt naar de kolom en niet naar 'er kwam geen fout': een lus
    die nul keer draait gooit ook niets, en dat is precies het stille falen dat
    hier niet mag."""
    engine = make_engine(database_url)
    _weg_ermee(engine, "documents", "filename")
    assert not _heeft_kolom(engine, "documents", "filename")
    bezet = threading.Event()
    t = threading.Thread(target=_lezer, args=(engine, 2.0, bezet))
    t.start()
    try:
        bezet.wait(5)
        init_schema(engine, attempts=20, lock_timeout="200ms", wait=0.3)
        assert _heeft_kolom(engine, "documents", "filename")
    finally:
        t.join()


def test_zero_attempts_is_refused_instead_of_quietly_doing_nothing():
    """Een lus die nul keer draait keert stil terug zonder migratie."""
    with pytest.raises(ValueError):
        init_schema(None, attempts=0)


def test_an_error_that_is_not_a_lock_is_not_retried(database_url):
    """Wachten maakt een onbereikbare database niet beter, en twintig pogingen
    zouden de echte fout tien minuten lang verbergen."""
    kapot = make_engine(database_url.rsplit("/", 1)[0] + "/bestaat_niet_ww")
    begin = time.monotonic()
    with pytest.raises(Exception):
        init_schema(kapot, attempts=20, wait=5.0)
    assert time.monotonic() - begin < 5, "er is gewacht op iets dat geen slot is"
