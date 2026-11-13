# SPDX-License-Identifier: MIT
"""The local demo harness (tools/demo): seeding is idempotent and yields the
promised dossier, and the console walk works over the stand-ins. DB-backed:
runs against a real Postgres and skips locally without one."""
import io
import os
import sys

import pypdf
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.models import AuditRecord, Dossier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from demo import corpus  # noqa: E402
from demo.seeds import grants, seed  # noqa: E402
from demo.wiring import StandIns, build_app  # noqa: E402

EXPECTED = {"documents": 31, "live": 28, "deleted": 2, "superseded": 1,
            "dossiers": 1, "topics": 6, "grants": 1}
VALUES = corpus.seeded_values(corpus.documents())


def _counts(report):
    return {k: report[k] for k in EXPECTED}


def test_seeding_an_empty_database_twice_is_idempotent(session_factory):
    first = seed(StandIns(session_factory, VALUES))
    assert first["seeded"] is True
    assert _counts(first) == EXPECTED
    # A second run -- new process, new stand-ins -- finds documents and leaves
    # every count where it was.
    second = seed(StandIns(session_factory, VALUES))
    assert second["seeded"] is False
    assert _counts(second) == EXPECTED


def test_the_console_walk_over_the_stand_ins(session_factory):
    stand_ins = StandIns(session_factory, VALUES)
    report = seed(stand_ins)
    doc = report["grant_document"]
    c = TestClient(build_app(stand_ins, {"k-mark": "mark", "k-gast": "gast"}),
                   follow_redirects=False, base_url="https://testserver")
    assert c.post("/console/login", data={"key": "k-mark"}).status_code == 303

    # Followed: /console may answer with the page or send on to the dossier.
    assert c.get("/console", follow_redirects=True).status_code == 200
    page = c.get("/console/search", params={
        "q": "Wanneer krijg ik als bewoner een parkeervergunning?",
        "dossier": "alle"}).text
    assert "parkeren.pdf" in page

    page = c.get(f"/console/documents/{doc}").text
    assert report["grant_id"] in page and "[PERSON:" in page

    pdf = c.get(f"/documents/{doc}/redacted.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    r = c.post(f"/documents/{doc}/reveal",
               json={"grant_id": report["grant_id"], "types": ["PERSON"]})
    assert r.status_code == 200, r.text
    assert r.json()["revealed_types"] == ["PERSON"]
    assert "[BSN:" in r.json()["revealed_text"]          # not asked, stays a token

    with session_factory() as s:
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.step == "deanonymize")).scalars().one()
    assert rec.payload["caller"] == "mark" and rec.payload["types"] == ["PERSON"]

    r = c.post(f"/documents/{doc}/reveal.pdf",
               json={"grant_id": report["grant_id"], "types": ["PERSON"]})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")

    # gast is logged in and may read nothing
    g = TestClient(c.app, follow_redirects=False, base_url="https://testserver")
    g.post("/console/login", data={"key": "k-gast"})
    assert g.get("/console", headers={"Accept": "text/html"}).status_code == 403
    assert g.get(f"/documents/{doc}/redacted.pdf").status_code == 403


def test_no_seeded_value_reaches_the_index_or_the_redacted_pdf(session_factory):
    stand_ins = StandIns(session_factory, VALUES)
    report = seed(stand_ins)
    with session_factory() as s:
        dossier_id = s.execute(select(Dossier.id)).scalar_one()
    texts = [d.text for d in stand_ins.index.documents_in(str(dossier_id))]
    assert len(texts) == EXPECTED["live"]
    for d in corpus.documents():
        for e in d.entities:
            value = d.text[e["start"]:e["end"]]
            assert not any(value in t for t in texts), (d.doc_id, e["type"])
    c = TestClient(build_app(stand_ins, {"k": "mark"}), base_url="https://testserver")
    c.post("/console/login", data={"key": "k"})
    pdf = c.get(f"/documents/{report['grant_document']}/redacted.pdf").content
    text = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)
    letter = next(d for d in corpus.documents() if d.doc_id == grants.DOCUMENT)
    for e in letter.entities:
        assert letter.text[e["start"]:e["end"]] not in text


def test_a_value_is_never_wrapped_over_two_lines():
    for d in corpus.documents():
        lines = corpus._lines(d)
        for e in d.entities:
            assert any(d.text[e["start"]:e["end"]] in line for line in lines)
