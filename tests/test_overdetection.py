"""redaction-overdetection: measurement harness, output format, counts-only
guard."""
from __future__ import annotations

from pathlib import Path

from wordsworth.eval.overdetection import (
    LABEL,
    WORDS,
    build_report,
    format_report,
    lists_comparison,
    word_counts,
    word_sentences,
)
from wordsworth.eval.overdetection_run import main, reachable
from wordsworth.eval.pii import load_gold
from wordsworth.openanonymiser_driver import Entity

FIX = Path(__file__).parent / "fixtures" / "pii_gold_synthetic.jsonl"
SEEDED_PERSON = "Janine van Dijk"


def _fake_word_detect(text: str) -> list[Entity]:
    """Types each of the five words the way the orchestrator described."""
    out = []
    if "statushouders" in text.lower():
        out.append(Entity("ORGANIZATION", "statushouders", 0, 1, "test", 0.9))
    if "bewoners" in text.lower():
        out.append(Entity("PERSON", "Bewoners", 0, 1, "test", 0.9))
        out.append(Entity("ORGANIZATION", "Bewoners", 0, 1, "test", 0.9))
    if "woningcorporaties" in text.lower():
        out.append(Entity("ORGANIZATION", "Woningcorporaties", 0, 1, "test", 0.9))
    if "juni" in text.lower():
        out.append(Entity("DATE_TIME", "juni", 0, 1, "test", 0.9))
    if "wereldvluchtelingendag" in text.lower():
        out.append(Entity("DATE_TIME", "wereldvluchtelingendag", 0, 1, "test", 0.9))
    return out


def test_word_sentences_cover_all_five_words():
    sentences = word_sentences()
    assert set(sentences) == set(WORDS)
    for word, text in sentences.items():
        assert word in text.lower()


def test_word_counts_tallies_by_type_only():
    counts = word_counts(word_sentences(), _fake_word_detect)
    assert counts["statushouders"] == {"ORGANIZATION": 1}
    assert counts["bewoners"] == {"PERSON": 1, "ORGANIZATION": 1}
    assert counts["juni"] == {"DATE_TIME": 1}
    assert counts["wereldvluchtelingendag"] == {"DATE_TIME": 1}


def test_word_counts_empty_when_never_detected():
    counts = word_counts(word_sentences(), lambda text: [])
    assert all(counts[w] == {} for w in WORDS)


def test_lists_comparison_runs_each_side_once():
    docs = load_gold(FIX)

    def without(text: str) -> list[Entity]:
        return [Entity("PERSON", "x", 0, 1, "test", 0.9)]

    def with_(text: str) -> list[Entity]:
        return []  # the list suppressed everything

    report = lists_comparison(docs, without, with_)
    assert report["without"]["span"]["PERSON"]["fp"] == len(docs)
    assert report["with"]["span"]["PERSON"]["fp"] == 0
    assert report["with"]["span"]["PERSON"]["tp"] == 0


def test_build_report_has_table_label_date_and_five_counts():
    docs = load_gold(FIX)
    report = build_report(docs, word_sentences(), _fake_word_detect,
                           _fake_word_detect, date="2026-10-30")
    out = format_report(report)
    assert LABEL in out
    assert "2026-10-30" in out
    assert "|" in out                       # a markdown table is present
    for word in WORDS:
        assert word in out


def test_format_report_not_run_has_no_table():
    out = format_report(None)
    assert "not run" in out
    assert "|" not in out
    assert LABEL in out


def test_counts_only_guard_no_seeded_value_in_output(caplog):
    docs = load_gold(FIX)
    assert any(SEEDED_PERSON in d.text for d in docs)   # the fixture does seed it

    def detect(text: str) -> list[Entity]:
        if SEEDED_PERSON in text:
            return [Entity("PERSON", SEEDED_PERSON, text.index(SEEDED_PERSON),
                            text.index(SEEDED_PERSON) + len(SEEDED_PERSON), "test", 0.9)]
        return []

    report = build_report(docs, word_sentences(), detect, detect, date="2026-10-30")
    out = format_report(report)
    assert SEEDED_PERSON not in out
    for doc in docs:
        assert doc.text not in out
    assert not any(SEEDED_PERSON in r.message for r in caplog.records)


def test_reachable_is_false_for_an_unreachable_url(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_OPENANONYMISER_URL", "http://127.0.0.1:1")
    assert reachable(timeout=1.0) is False


def test_main_reports_not_run_when_unreachable(tmp_path, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_OPENANONYMISER_URL", "http://127.0.0.1:1")
    out_path = tmp_path / "report.md"
    assert main([str(FIX), "--out", str(out_path)]) == 0
    text = out_path.read_text(encoding="utf-8")
    assert "not run" in text
    assert "|" not in text


def test_doc_file_has_label_table_layout_and_not_run_state():
    doc = Path(__file__).parent.parent / "docs" / "explanation" / "meting-overdetectie-07.md"
    text = doc.read_text(encoding="utf-8")
    assert LABEL in text
    assert "not run" in text
    assert "| type |" in text and "| woord |" in text
    for word in WORDS:
        assert word in text
