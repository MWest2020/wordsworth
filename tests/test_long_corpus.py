# SPDX-License-Identifier: MIT
"""The long synthetic PDF corpus and its page-level ground truth
(synthetic-long-corpus)."""
import importlib.util
import json
import re
from pathlib import Path

import pypdfium2 as pdfium

from wordsworth.detectors import find_deterministic
from wordsworth.eval.collection import load_qrels, load_queries
from wordsworth.eval.pii import load_gold
from wordsworth.pdf_text import page_text

_spec = importlib.util.spec_from_file_location(
    "generate_long_corpus",
    Path(__file__).resolve().parents[1] / "scripts/eval/generate_long_corpus.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

_CREATION_DATE_RE = re.compile(rb"/CreationDate\s*\(D\\0722000.*?\)")


def _page_texts(pdf_path: Path) -> list[str]:
    """Every page's text, extracted exactly as `profiling.py` iterates pages."""
    pdf = pdfium.PdfDocument(pdf_path.read_bytes())
    try:
        texts = []
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            try:
                texts.append(page_text(textpage))
            finally:
                textpage.close()
                page.close()
        return texts
    finally:
        pdf.close()


def test_generator_writes_the_files_pages_header_footer_and_watermark(tmp_path):
    long_docs = gen.generate(tmp_path, docs=2, pages=6, seed=1, scanned=0.0)
    assert len(long_docs) == 2
    for ld in long_docs:
        pdf_path = tmp_path / "documents" / f"{ld.doc_id}.pdf"
        assert pdf_path.exists()
        texts = _page_texts(pdf_path)
        assert len(texts) == 6
        for page_no, txt in enumerate(texts, start=1):
            assert "SYNTHETISCH" in txt
            assert f"pagina {page_no} van 6" in txt
            assert re.search(r"WOO-\d{4}-\d{4}", txt)
    for name in ("gold.jsonl", "gold_scanned.jsonl", "queries.tsv", "qrels.txt",
                 "manifest.json"):
        assert (tmp_path / name).exists()


def test_gold_is_true(tmp_path):
    """Every gold value of a born-digital page is a substring of that page's
    extracted text; every scanned page is empty, in gold_scanned and not in
    gold, and page 1 is never scanned."""
    long_docs = gen.generate(tmp_path, docs=4, pages=6, seed=3, scanned=0.5)
    gold = {d.id: d for d in load_gold(tmp_path / "gold.jsonl")}
    gold_scanned_raw = {r["id"]: r for r in
                        (json.loads(l) for l in
                         (tmp_path / "gold_scanned.jsonl").read_text(
                             encoding="utf-8").splitlines())}
    assert gold_scanned_raw  # the 0.5 fraction must have produced some

    for ld in long_docs:
        assert 1 not in ld.scanned
        texts = _page_texts(tmp_path / "documents" / f"{ld.doc_id}.pdf")
        for page_no, txt in enumerate(texts, start=1):
            page_id = f"{ld.doc_id}#p{page_no:02d}"
            if page_no in ld.scanned:
                assert txt == ""
                assert page_id in gold_scanned_raw
                assert page_id not in gold
            else:
                assert page_id in gold
                assert page_id not in gold_scanned_raw
                doc = gold[page_id]
                for span in doc.entities:
                    assert doc.text[span.start:span.end] in txt


def test_no_unplanned_bsn_or_postcode(tmp_path):
    gen.generate(tmp_path, docs=3, pages=30, seed=20261106, scanned=0.1)
    for raw in (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(raw)
        found = {(lbl.upper(), s, e) for lbl, _, s, e in find_deterministic(doc["text"])
                 if lbl.upper() in ("BSN", "POSTCODE")}
        wanted = {(e["type"], e["start"], e["end"]) for e in doc["entities"]
                  if e["type"] in ("BSN", "POSTCODE")}
        assert found == wanted, doc["id"]


def test_queries_answer_a_late_unique_page(tmp_path):
    """`--pages 22` exercises the >= page 20 branch."""
    long_docs = gen.generate(tmp_path, docs=3, pages=22, seed=5, scanned=0.1)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    queries = load_queries(tmp_path / "queries.tsv")
    qrels = load_qrels(tmp_path / "qrels.txt")

    assert len(manifest["queries"]) == 3
    assert set(queries) == set(qrels) == {q["query_id"] for q in manifest["queries"]}
    assert all(len(judged) == 3 for judged in qrels.values())

    all_texts = {ld.doc_id: _page_texts(tmp_path / "documents" / f"{ld.doc_id}.pdf")
                for ld in long_docs}
    for q in manifest["queries"]:
        assert q["answer_page"] >= 20
        answer_text = all_texts[q["doc_id"]][q["answer_page"] - 1]
        assert q["answer_phrase"] in answer_text
        # unique across the whole corpus
        hits = sum(1 for doc_id, texts in all_texts.items() for t in texts
                   if q["answer_phrase"] in t)
        assert hits == 1
        judged = qrels[q["query_id"]]
        assert judged[q["doc_id"]] == 1
        assert sum(judged.values()) == 1


def test_generation_is_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gen.generate(a, docs=2, pages=6, seed=9, scanned=0.3)
    gen.generate(b, docs=2, pages=6, seed=9, scanned=0.3)
    for name in ("gold.jsonl", "gold_scanned.jsonl", "queries.tsv", "qrels.txt",
                 "manifest.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    for pdf in sorted((a / "documents").glob("*.pdf")):
        pdf_bytes = pdf.read_bytes()
        assert pdf_bytes == (b / "documents" / pdf.name).read_bytes()
        assert _CREATION_DATE_RE.search(pdf_bytes), "creation date must be the invariant constant"
