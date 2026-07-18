import json

from wordsworth.pipeline import ingest, process
from wordsworth.states import State
from wordsworth.structured_log import log_transition


def test_log_transition_returns_parseable_json_with_id_and_step():
    line = log_transition(
        document_id="d1",
        from_state="registered",
        to_state="extractable",
        step="profile",
        duration_ms=12.5,
    )
    data = json.loads(line)
    assert data["document_id"] == "d1"
    assert data["step"] == "profile"
    assert data["from"] == "registered"
    assert data["to"] == "extractable"
    assert data["duration_ms"] == 12.5
    assert data["level"] == "info"


def test_failed_transition_logs_at_error_level():
    data = json.loads(
        log_transition(
            document_id="d1",
            from_state="registered",
            to_state="failed",
            step="profile",
            duration_ms=None,
            level="error",
        )
    )
    assert data["to"] == "failed"
    assert data["level"] == "error"


def test_pipeline_transition_emits_structured_line(
    session, born_digital_pdf, mem_store, mem_index, fake_embedder, caplog
):
    doc = ingest(session, mem_store, born_digital_pdf)
    session.commit()
    with caplog.at_level("INFO", logger="wordsworth.pipeline"):
        final = process(
            session, doc.id, mem_store,
            search_index=mem_index, embedder=fake_embedder,
        )
    session.commit()
    assert final == State.INDEXED

    lines = [json.loads(r.getMessage()) for r in caplog.records]
    lines = [d for d in lines if d.get("event") == "transition"]
    assert lines, "expected at least one transition log line"
    for d in lines:
        assert d["document_id"] == str(doc.id)
        assert d["step"]
    steps = {d["step"] for d in lines}
    assert {"profile", "extract", "anonymize", "index"} <= steps
