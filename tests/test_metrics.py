from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.metrics import render_metrics
from wordsworth.pipeline import process, register


def _build(session_factory, fixtures, mem_index, fake_embedder):
    with session_factory() as s:
        for name, data in fixtures:
            doc = register(s, name)
            s.commit()
            process(s, doc.id, data, search_index=mem_index, embedder=fake_embedder)
            s.commit()


def test_metrics_per_state_counts_match_documents(
    session_factory, born_digital_pdf, scanned_pdf, corrupt_pdf,
    mem_index, fake_embedder,
):
    _build(
        session_factory,
        [("born", born_digital_pdf), ("scan", scanned_pdf), ("bad", corrupt_pdf)],
        mem_index, fake_embedder,
    )
    client = TestClient(create_app(session_factory=session_factory))
    resp = client.get("/metrics")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert 'wordsworth_documents_total{state="indexed"} 1' in body
    assert 'wordsworth_documents_total{state="unprocessable_ocr"} 1' in body
    assert 'wordsworth_documents_total{state="failed"} 1' in body
    assert "wordsworth_failed_total 1" in body
    # register fired once per document.
    assert 'wordsworth_transitions_total{step="register"} 3' in body


def test_render_metrics_has_prometheus_help_and_type(
    session_factory, born_digital_pdf, mem_index, fake_embedder,
):
    _build(session_factory, [("born", born_digital_pdf)], mem_index, fake_embedder)
    with session_factory() as s:
        body = render_metrics(s)
    assert "# HELP wordsworth_documents_total" in body
    assert "# TYPE wordsworth_documents_total gauge" in body
    assert "# TYPE wordsworth_transitions_total counter" in body


def test_metrics_absent_without_session_factory():
    # No DB wired -> the endpoint is not registered at all.
    client = TestClient(create_app())
    assert client.get("/metrics").status_code == 404
