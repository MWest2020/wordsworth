# SPDX-License-Identifier: MIT
"""Assemble a long-corpus document's pages, its per-page gold and its query
(long_corpus_parts.py builds page content, long_corpus_pdf.py draws it).

One `Document` per page (synthetic.py): a header line (document number,
`SYNTHETISCH`) and a footer line (`pagina x van y`) wrapped around one part
builder's output. The gold `text` is NOT this `Document`'s own text -- it is
that page's text read back from the rendered PDF via `pdf_text.page_text`,
the exact string the detectors scan. Each gold offset is found by locating
the planted value in that extracted text; a value not found exactly once
fails the generator (`_extract_gold`), which is the one invariant every
other gold check in this change rests on.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import pypdfium2 as pdfium

from ..pdf_text import page_text
from .long_corpus_parts import (build_cover, build_email_thread, build_letter,
                                build_minutes, build_table, build_toc)
from .long_corpus_pdf import render_final_pdf, render_source_pdf
from .synthetic import Document

_BODY_PARTS = [build_letter, build_email_thread, build_minutes, build_table]


@dataclass
class PageGold:
    id: str
    doc: str
    page: int
    text: str
    entities: list[dict] = field(default_factory=list)

    def record(self) -> dict:
        return {"id": self.id, "doc": self.doc, "page": self.page,
                "text": self.text, "entities": self.entities}


@dataclass
class DocResult:
    doc_id: str
    pdf_bytes: bytes
    gold_pages: list[PageGold]
    gold_scanned_pages: list[PageGold]
    scanned_pages: list[int]
    answer_page: int
    answer_phrase: str


def _page_width(total_pages: int) -> int:
    return max(2, len(str(total_pages)))


def _builder_for(page: int, pages: int):
    if page == 1:
        return build_cover
    if page == 2 and pages > 2:
        return build_toc
    offset = 3 if pages > 2 else 2
    return _BODY_PARTS[(page - offset) % len(_BODY_PARTS)]


def _build_page(rng: random.Random, doc_number: str, page: int, total_pages: int,
                answer_phrase: str | None) -> Document:
    body = _builder_for(page, total_pages)(rng, doc_number)
    if answer_phrase is not None:
        body.lit(f"\nUnieke vindplaats: {answer_phrase}.\n")

    width = _page_width(total_pages)
    container = Document(f"{doc_number}-p{page:0{width}d}", "")
    container.lit(f"{doc_number}  SYNTHETISCH\n\n")
    base = len(container.text)
    container.text += body.text
    for e in body.entities:
        container.entities.append({"start": e["start"] + base,
                                    "end": e["end"] + base, "type": e["type"]})
    container.types |= body.types
    container.lit(f"\n\npagina {page} van {total_pages}\n")
    return container.check()


def _choose_answer(doc_id: str, pages: int, rng: random.Random) -> tuple[int, str]:
    answer_page = rng.randint(20, pages) if pages >= 20 else pages
    suffix = rng.randrange(1000, 9999)
    return answer_page, f"codetermijn-{doc_id}-{suffix}"


def _choose_scanned(pages: int, answer_page: int, fraction: float,
                    rng: random.Random) -> list[int]:
    """Never page 1, never the answer page -- its planted phrase must always
    have a text layer for the query mechanism to measure anything."""
    candidates = [p for p in range(2, pages + 1) if p != answer_page]
    count = int(fraction * pages)
    return sorted(rng.sample(candidates, k=min(count, len(candidates))))


def _extract_gold(doc_id: str, page_docs: list[Document], source_bytes: bytes,
                  scanned_pages: list[int]) -> tuple[list[PageGold], list[PageGold]]:
    pdf = pdfium.PdfDocument(source_bytes)
    try:
        texts = []
        for i in range(len(pdf)):
            page = pdf[i]
            tp = page.get_textpage()
            try:
                texts.append(page_text(tp))
            finally:
                tp.close()
                page.close()
    finally:
        pdf.close()

    width = _page_width(len(page_docs))
    gold: list[PageGold] = []
    gold_scanned: list[PageGold] = []
    for i, (doc, text) in enumerate(zip(page_docs, texts), start=1):
        entities = []
        for e in doc.entities:
            value = doc.text[e["start"]:e["end"]]
            if text.count(value) != 1:
                raise ValueError(
                    f"{doc_id} page {i}: {e['type']} value {value!r} found "
                    f"{text.count(value)} times in the extracted text, want exactly 1")
            start = text.index(value)
            entities.append({"start": start, "end": start + len(value), "type": e["type"]})
        record = PageGold(f"{doc_id}#p{i:0{width}d}", doc_id, i, text, entities)
        (gold_scanned if i in scanned_pages else gold).append(record)
    return gold, gold_scanned


def build_document(doc_id: str, doc_number: str, pages: int, scanned_fraction: float,
                   rng: random.Random) -> DocResult:
    answer_page, answer_phrase = _choose_answer(doc_id, pages, rng)
    page_docs = [
        _build_page(rng, doc_number, page, pages,
                    answer_phrase if page == answer_page else None)
        for page in range(1, pages + 1)
    ]
    scanned_pages = _choose_scanned(pages, answer_page, scanned_fraction, rng)

    source_bytes = render_source_pdf(doc_number, page_docs)
    gold_pages, gold_scanned_pages = _extract_gold(doc_id, page_docs, source_bytes,
                                                    scanned_pages)
    final_bytes = render_final_pdf(doc_number, page_docs, source_bytes, scanned_pages)

    return DocResult(doc_id, final_bytes, gold_pages, gold_scanned_pages,
                     scanned_pages, answer_page, answer_phrase)
