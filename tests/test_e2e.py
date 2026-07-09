from wordsworth import audit
from wordsworth.pipeline import ingest, process
from wordsworth.report import run_report
from wordsworth.states import State


def test_end_to_end_three_terminal_states(session, born_digital_pdf,
                                          scanned_pdf, corrupt_pdf, mem_index,
                                          fake_embedder, mem_store):
    fixtures = {
        "born": born_digital_pdf,
        "scan": scanned_pdf,
        "bad": corrupt_pdf,
    }
    ids = {}
    for name, data in fixtures.items():
        doc = ingest(session, mem_store, data)
        session.commit()
        ids[name] = doc.id

    finals = {}
    for name, did in ids.items():
        finals[name] = process(session, did, mem_store, search_index=mem_index,
                               embedder=fake_embedder)
        session.commit()

    assert finals["born"] == State.INDEXED
    assert finals["scan"] == State.UNPROCESSABLE_OCR
    assert finals["bad"] == State.FAILED

    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None

    report = run_report(session)
    assert report["total_documents"] == 3
    assert report["current_states"]["indexed"] == 1
    assert report["current_states"]["unprocessable_ocr"] == 1
    assert report["current_states"]["failed"] == 1
    assert report["born_digital_share"] == 0.5
    assert report["pages"]["count"] == 2
