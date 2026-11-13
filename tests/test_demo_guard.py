# SPDX-License-Identifier: MIT
"""What the local demo (tools/demo) refuses: databases that are not demo or test
databases, a database seeded by an earlier run, leftover WORDSWORTH_* settings,
and documents from outside. The URL checks run without a database; the rest is
DB-backed and skips locally without one."""
import hashlib
import io
import os
import re
import sys

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from wordsworth.db import make_engine
from wordsworth.models import Document

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from demo import corpus  # noqa: E402
from demo.guard import (Refused, check_database, check_url,  # noqa: E402
                        clear_environment, connected_name, refuse_if_held)
from demo.seeds import seed  # noqa: E402
from demo.wiring import StandIns, build_app  # noqa: E402

VALUES = corpus.seeded_values(corpus.documents())


@pytest.mark.parametrize("url, why", [
    ("postgresql://u:p@h/wordsworth_demo", "postgresql+psycopg"),
    ("postgresql+psycopg://u:p@h/ww_demo", "only runs on a database named"),
    ("postgresql+psycopg://u:p@h/wordsworth", "only runs on a database named"),
    ("postgresql+psycopg://u:p@h/", "only runs on a database named"),
    # The path names a demo database, the parameter connects to another.
    ("postgresql+psycopg://u:p@h/wordsworth_demo?dbname=wordsworth", "no query"),
    ("postgresql+psycopg://u:p@h/wordsworth_demo?service=prod", "no query"),
])
def test_the_url_guard_refuses_before_connecting(url, why):
    with pytest.raises(Refused, match=re.escape(why)):
        check_url(url)


def test_the_url_guard_lets_a_demo_or_test_database_through():
    assert check_url("postgresql+psycopg://u:p@h/wordsworth_demo_x") == "wordsworth_demo_x"
    assert check_url("postgresql+psycopg://u:p@h/wordsworth_test_y") == "wordsworth_test_y"


def test_the_connected_name_is_checked_too():
    with pytest.raises(Refused, match="not 'wordsworth'"):
        check_database("wordsworth")


def test_the_connected_name_is_what_the_server_reports(database_url):
    engine = make_engine(database_url)
    try:
        assert connected_name(engine) == make_url(database_url).database
    finally:
        engine.dispose()


def test_leftover_settings_are_cleared(monkeypatch):
    # Registered with monkeypatch first, so every variable this clears --
    # WORDSWORTH_TEST_DATABASE_URL included -- comes back for the next test.
    for k in [k for k in os.environ if k.startswith("WORDSWORTH_")]:
        monkeypatch.setenv(k, os.environ[k])
    monkeypatch.setenv("WORDSWORTH_ALLOW_GLOBAL_GRANTS", "1")
    monkeypatch.setenv("WORDSWORTH_X_DEMO_PROBE", "y")
    cleared = clear_environment()
    assert {"WORDSWORTH_ALLOW_GLOBAL_GRANTS", "WORDSWORTH_X_DEMO_PROBE"} <= set(cleared)
    assert not [k for k in os.environ if k.startswith("WORDSWORTH_")]


def test_a_database_seeded_by_an_earlier_run_is_refused(session_factory):
    seed(StandIns(session_factory, VALUES))
    with pytest.raises(Refused, match="already holds 31 documents"):
        refuse_if_held(session_factory, "wordsworth_demo")


def test_an_empty_database_is_not_refused(session_factory):
    refuse_if_held(session_factory, "wordsworth_demo")


def _pdf(line: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(60, 800, line)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_ingest_is_refused_at_the_edge_for_every_caller(session_factory):
    """No row, no stored original, nothing in the index: refused before a route runs."""
    stand_ins = StandIns(session_factory, VALUES)
    seed(stand_ins)
    app = build_app(stand_ins, {"k-mark": "mark", "k-gast": "gast"})
    name = "Zwaantje Oostergoo"                       # not a seeded value
    pdf = _pdf(f"Dit besluit betreft {name}, wonend te Nergenshuizen.")

    def documents():
        with session_factory() as s:
            return s.execute(select(func.count()).select_from(Document)).scalar_one()

    before = documents()
    for key in ("k-mark", "k-gast", None):
        c = TestClient(app, base_url="https://testserver")
        if key:
            c.post("/console/login", data={"key": key})
        for path in ("/ingest", "/ingest/"):
            r = c.post(path, files={"files": ("x.pdf", pdf, "application/pdf")})
            assert r.status_code == 403 and "does not ingest" in r.json()["detail"]
    assert documents() == before
    key = "documents/" + hashlib.sha256(pdf).hexdigest()
    assert not stand_ins.store.exists(key)
    assert not stand_ins.index.has_object_key(key)
