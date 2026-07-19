from wordsworth.pipeline import ingest, process
from wordsworth.report import run_report


def test_report_includes_throughput_and_stage_timing(
    session, born_digital_pdf, scanned_pdf, mem_store, mem_index, fake_embedder,
):
    for data in [born_digital_pdf, scanned_pdf]:
        doc = ingest(session, mem_store, data)
        session.commit()
        process(session, doc.id, mem_store, search_index=mem_index,
                embedder=fake_embedder)
        session.commit()

    report = run_report(session)

    # Throughput fields present.
    assert "docs_per_hour" in report
    assert "elapsed_hours" in report
    assert report["elapsed_hours"] is not None
    assert report["elapsed_hours"] >= 0

    # Per-stage timing present and covering the real pipeline stages.
    timing = report["stage_timing"]
    assert "profile" in timing
    for stage in timing.values():
        assert "count" in stage
        assert "mean_ms" in stage
        assert "p95_ms" in stage
        assert stage["mean_ms"] >= 0
    # register is the first transition per doc -> no preceding gap, excluded.
    assert "register" not in timing
