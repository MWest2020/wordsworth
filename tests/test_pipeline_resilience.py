"""Pipeline + batch resilience (pipeline-resilience). DB-integration — runs in CI
against real Postgres; skips locally without a DB."""
from __future__ import annotations

import io

import pytest

from wordsworth.anonymizer import AnonymizationResult
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.pipeline import current_state, get_anonymized_text, ingest, process
from wordsworth.states import State


class _Anon:
    """Anonymizer double: fails the first `fail_times` calls with `exc`, then
    returns a redacted (PII-free) result."""

    def __init__(self, fail_times: int, exc: Exception):
        self.calls = 0
        self._fail_times = fail_times
        self._exc = exc

    def anonymize(self, text: str) -> AnonymizationResult:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._exc
        return AnonymizationResult(text="REDACTED", counts={})


def test_transient_blip_is_retried_to_indexed(
    session, born_digital_pii_pdf, mem_index, fake_embedder, mem_store, monkeypatch
):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")  # no real sleeps
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    anon = _Anon(fail_times=2, exc=AnonymizationEngineError("blip"))  # ok on try 3
    final = process(session, doc.id, mem_store, anonymizer=anon,
                    search_index=mem_index, embedder=fake_embedder)
    session.commit()
    assert final == State.INDEXED
    assert anon.calls == 3  # two transient blips absorbed, third succeeded


def test_persistent_outage_stays_resumable_and_never_indexes(
    session, born_digital_pii_pdf, mem_index, fake_embedder, mem_store, monkeypatch
):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    anon = _Anon(fail_times=99, exc=AnonymizationEngineError("down"))
    with pytest.raises(AnonymizationEngineError):
        process(session, doc.id, mem_store, anonymizer=anon,
                search_index=mem_index, embedder=fake_embedder)
    session.rollback()  # caller closes without commit → last committed state stands
    assert current_state(session, doc.id) == State.REGISTERED  # resumable
    assert mem_index._docs == {}                               # nothing indexed
    assert get_anonymized_text(session, doc.id) is None        # no text persisted


def test_permanent_error_is_not_retried_in_pipeline(
    session, born_digital_pii_pdf, mem_index, fake_embedder, mem_store
):
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    anon = _Anon(fail_times=99, exc=ValueError("logic bug"))
    with pytest.raises(ValueError):
        process(session, doc.id, mem_store, anonymizer=anon,
                search_index=mem_index, embedder=fake_embedder)
    assert anon.calls == 1  # permanent error → no retry


# --- batch continues past a failing document -------------------------------

def _pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 800, text)
    c.showPage()
    c.save()
    return buf.getvalue()


class _MarkerAnon:
    """Fails (transiently) for any text containing FAILME; redacts otherwise."""

    def anonymize(self, text: str) -> AnonymizationResult:
        if "FAILME" in text:
            raise AnonymizationEngineError("downstream down")
        return AnonymizationResult(text="REDACTED", counts={})


def test_batch_continues_past_a_failing_document(
    session_factory, mem_index, fake_embedder, mem_store, monkeypatch
):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app

    app = create_app(session_factory=session_factory, search_index=mem_index,
                     embedder=fake_embedder, store=mem_store, anonymizer=_MarkerAnon())
    client = TestClient(app)
    ok_pdf = _pdf("Een net document met tekst, niets mis.")
    bad_pdf = _pdf("Dit document bevat FAILME en de dienst ligt plat.")

    resp = client.post("/ingest", files=[
        ("files", ("ok.pdf", ok_pdf, "application/pdf")),
        ("files", ("bad.pdf", bad_pdf, "application/pdf")),
    ])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2                 # batch not aborted by the failure
    states = {r["filename"]: r["state"] for r in body["results"]}
    assert states["ok.pdf"] == "indexed"
    assert states["bad.pdf"] == "retryable"   # transient → retryable, not error
    # nothing from the failing document leaked into the index
    assert all("FAILME" not in text for text, _k, _v in mem_index._docs.values())
