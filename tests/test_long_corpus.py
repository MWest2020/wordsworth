# SPDX-License-Identifier: MIT
"""The long synthetic PDF corpus and its page-level ground truth
(synthetic-long-corpus)."""
import importlib.util
import json
import random
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from wordsworth.detectors import find_deterministic
from wordsworth.eval.collection import load_qrels, load_queries
from wordsworth.eval.long_corpus import build_document
from wordsworth.eval.pii import load_gold
from wordsworth.pdf_text import page_text

_spec = importlib.util.spec_from_file_location(
    "generate_long_corpus",
    Path(__file__).resolve().parents[1] / "scripts/eval/generate_long_corpus.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

_GENERATOR_FILES = [
    Path("src/wordsworth/eval/long_corpus.py"),
    Path("src/wordsworth/eval/long_corpus_parts.py"),
    Path("src/wordsworth/eval/long_corpus_pdf.py"),
    Path("src/wordsworth/eval/synthetic.py"),
    Path("scripts/eval/generate_long_corpus.py"),
]
_REPO_ROOT = Path(__file__).resolve().parents[1]

# reportlab's invariant mode writes this fixed epoch instead of wall-clock.
_INVARIANT_CREATION_DATE = "D:20000101000000+00'00'"


def _pages_of(path: Path) -> pdfium.PdfDocument:
    return pdfium.PdfDocument(path.read_bytes())


def _page_texts(pdf: pdfium.PdfDocument) -> list[str]:
    texts = []
    for i in range(len(pdf)):
        page = pdf[i]
        tp = page.get_textpage()
        try:
            texts.append(page_text(tp))
        finally:
            tp.close()
            page.close()
    return texts


def test_generator_writes_the_files_with_the_right_shape(tmp_path):
    gen.main([str(tmp_path), "--docs", "2", "--pages", "6", "--seed", "1"])
    for name in ("gold.jsonl", "gold_scanned.jsonl", "queries.tsv", "qrels.txt",
                "manifest.json"):
        assert (tmp_path / name).exists()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for doc_id in manifest["pages_per_document"]:
        pdf_path = tmp_path / "documents" / f"{doc_id}.pdf"
        assert pdf_path.exists()
        pdf = _pages_of(pdf_path)
        assert len(pdf) == 6
        doc_number = f"WOO-2026-{int(doc_id.split('-')[1]) + 1:04d}"
        for i, text in enumerate(_page_texts(pdf), start=1):
            assert doc_number in text
            assert "SYNTHETISCH" in text
            assert f"pagina {i} van 6" in text


def test_gold_text_is_the_pages_extracted_text(tmp_path):
    gen.main([str(tmp_path), "--docs", "2", "--pages", "6", "--seed", "1"])
    docs = load_gold(tmp_path / "gold.jsonl")        # range check must hold
    assert len(docs) > 0
    for doc in docs:
        doc_id, _, page = doc.id.partition("#p")
        pdf = _pages_of(tmp_path / "documents" / f"{doc_id}.pdf")
        text = _page_texts(pdf)[int(page) - 1]
        assert doc.text == text
        for e in doc.entities:
            value = doc.text[e.start:e.end]
            assert text.count(value) == 1


def test_gold_is_true_with_scanned_pages(tmp_path):
    gen.main([str(tmp_path), "--docs", "2", "--pages", "6", "--scanned", "0.5",
             "--seed", "1"])
    gold = load_gold(tmp_path / "gold.jsonl")
    gold_scanned = load_gold(tmp_path / "gold_scanned.jsonl")
    assert len(gold_scanned) > 0        # the default would round down to none

    gold_pages = {d.id for d in gold}
    scanned_pages = {d.id for d in gold_scanned}
    assert gold_pages.isdisjoint(scanned_pages)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for doc_id, pages in manifest["scanned_pages_per_document"].items():
        assert 1 not in pages
        pdf = _pages_of(tmp_path / "documents" / f"{doc_id}.pdf")
        texts = _page_texts(pdf)
        for p in pages:
            assert texts[p - 1] == ""
            assert f"{doc_id}#p{p:02d}" in scanned_pages
            assert f"{doc_id}#p{p:02d}" not in gold_pages


def test_scanned_pages_are_rasterised_images(tmp_path):
    gen.main([str(tmp_path), "--docs", "1", "--pages", "6", "--scanned", "0.5",
             "--seed", "1"])
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    doc_id = next(iter(manifest["scanned_pages_per_document"]))
    pages = manifest["scanned_pages_per_document"][doc_id]
    assert pages
    pdf = _pages_of(tmp_path / "documents" / f"{doc_id}.pdf")
    for p in pages:
        page = pdf[p - 1]
        objs = list(page.get_objects())
        assert any(isinstance(o, pdfium.PdfImage) for o in objs)
        page.close()
    assert len(pdf) == manifest["pages_per_document"][doc_id]


@pytest.mark.parametrize("seed", range(1, 8))
def test_the_answer_page_is_never_scanned(seed):
    rng = random.Random(seed)
    for i in range(2):
        result = build_document(f"doc-{i:04d}", f"WOO-2026-{i + 1:04d}", 22, 0.3, rng)
        assert result.answer_page not in result.scanned_pages
        assert 1 not in result.scanned_pages
        assert 20 <= result.answer_page <= 22


@pytest.mark.parametrize("path", _GENERATOR_FILES, ids=str)
def test_generator_files_stay_under_200_lines(path):
    assert len((_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()) <= 200


@pytest.mark.parametrize("path", _GENERATOR_FILES[:3], ids=str)
def test_every_canvas_is_invariant(path):
    source = (_REPO_ROOT / path).read_text(encoding="utf-8")
    for line in source.splitlines():
        if "Canvas(" in line:
            assert "invariant=1" in line


def test_pdf_creation_date_is_the_invariant_constant(tmp_path):
    gen.main([str(tmp_path), "--docs", "1", "--pages", "6", "--seed", "1"])
    pdf = _pages_of(tmp_path / "documents" / "doc-0000.pdf")
    assert pdf.get_metadata_dict()["CreationDate"] == _INVARIANT_CREATION_DATE


def test_detections_equal_gold_exactly(tmp_path):
    gen.main([str(tmp_path), "--docs", "2", "--pages", "6", "--seed", "1"])
    deterministic = {"BSN", "IBAN", "EMAIL", "POSTCODE"}
    for raw in (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(raw)
        found = {(s, e, lbl.upper()) for lbl, _, s, e in find_deterministic(doc["text"])}
        wanted = {(e["start"], e["end"], e["type"]) for e in doc["entities"]
                  if e["type"] in deterministic}
        assert found == wanted, doc["id"]


def test_queries_are_the_planted_phrase_verbatim(tmp_path):
    gen.main([str(tmp_path), "--docs", "2", "--pages", "22", "--seed", "1"])
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    queries = load_queries(tmp_path / "queries.tsv")
    qrels = load_qrels(tmp_path / "qrels.txt")

    all_texts = {}
    for q in manifest["queries"]:
        pdf = _pages_of(tmp_path / "documents" / f"{q['doc_id']}.pdf")
        all_texts[q["doc_id"]] = _page_texts(pdf)

    for q in manifest["queries"]:
        assert q["answer_page"] >= 20
        assert queries[q["query_id"]] == q["answer_phrase"]
        assert q["answer_phrase"] in all_texts[q["doc_id"]][q["answer_page"] - 1]
        for other_id, texts in all_texts.items():
            if other_id != q["doc_id"]:
                assert all(q["answer_phrase"] not in t for t in texts)

    assert set(qrels) == {q["query_id"] for q in manifest["queries"]}
    doc_ids = set(manifest["pages_per_document"])
    assert all(set(judged) == doc_ids for judged in qrels.values())


def test_generation_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gen.main([str(a), "--docs", "2", "--pages", "6", "--scanned", "0.5", "--seed", "9"])
    gen.main([str(b), "--docs", "2", "--pages", "6", "--scanned", "0.5", "--seed", "9"])
    for name in ("gold.jsonl", "gold_scanned.jsonl", "queries.tsv", "qrels.txt",
                "manifest.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    for pdf_path in sorted((a / "documents").glob("*.pdf")):
        assert pdf_path.read_bytes() == (b / "documents" / pdf_path.name).read_bytes()
