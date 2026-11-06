# synthetic-long-corpus

## Why

Mark, 2026-11-06: "kunnen we ook een eval-dataset genereren voor testen? 30
documenten met 30 pagina's of zo."

The existing generator (`scripts/eval/generate_ground_truth.py`) writes ~500
*short text* documents. Real Woo publications are long PDFs: covers, e-mail
threads, minutes, tables, page headers and footers, and scanned pages. Page
boundaries, long-document ranking and pages without a text layer are what a
short-text corpus cannot test.

## What changes

- **`scripts/eval/generate_long_corpus.py <outdir> --docs 30 --pages 30 --seed N
  [--scanned 0.1]`** writes:
  - `documents/<doc-id>.pdf`: born-digital PDFs of `--pages` pages each, built from
    realistic Woo parts (a cover page, a table of contents, letters, e-mail threads,
    minutes, tables), with a page header and footer on every page: "pagina x van y",
    a document number shaped `WOO-<year>-<4 digits>` (never a bare 9-digit number or
    a postcode shape, which the detectors would read as a BSN or a postcode), and
    the word `SYNTHETISCH`.
  - **scanned pages, mixed into otherwise born-digital documents.** `--scanned` is a
    fraction *per document*, rounded down, drawn from the seed, never page 1 (the
    cover) and never the page holding the planted answer; default 0.1 = 3 pages of a 30-page document. Each chosen page is
    rendered by pdfium (pypdfium2, as in `pdf_render.py`) from its text and re-embedded
    as an image-only page via Pillow, so it has no text layer. What this tests: such a document
    is still classified born-digital (`profile_pdf` counts characters per document),
    so it never reaches OCR and **those pages are lost without a trace**. It does not
    exercise OCR; whole scanned documents for OCR recovery are a later change.
  - `gold.jsonl`: **one line per born-digital page**, in exactly the format
    `wordsworth.eval.pii` `load_gold` reads, plus two keys it ignores:
    `{"id": "<doc-id>#p<NN>", "doc": "<doc-id>", "page": N, "text": "<that page's
    text>", "entities": [{"start", "end", "type"}]}`. `text` is the page's
    extracted text (`wordsworth.pdf_text.page_text` over the pypdfium2 page), the exact
    string the detectors scan, and the offsets are character offsets into it. For a
    born-digital page the gold text IS the extracted text: the generator plants values,
    then computes each offset by locating the value in the extracted text, and a value
    not found exactly once fails the generator. So `load_gold`'s range check holds.
    Consequences, stated so a number is read right: `pii_run` reports
    `documents=<number of pages>` (about 900 for 30×30, minus scanned pages), and
    gold ids are not qrels ids: qrels use the PDF stem, the gold the page id, and the
    document is in the `doc` field.
  - `gold_scanned.jsonl`: the same records for the scanned pages, kept apart (their
    `text` is the text that was rasterised, as there is no text layer to extract). They
    are **not** part of the score to quote: `pii_run` detects over gold text and never
    opens a PDF, so scoring them would count pages the pipeline cannot see as if
    extraction were perfect.
  - `queries.tsv` and `qrels.txt`: one query per document, whose only answer is a
    unique phrase planted on a page at or after page 20 (or the last page of a shorter
    document). The query text is that planted phrase verbatim. Every document is judged
    for every query, non-relevant as 0, as the existing generator does. **What it is for:** long-document ranking fairness
    (`long-documents-rank-fairly`): a long document must still rank when its one
    matching passage is deep inside it. `wordsworth.eval.run` scores whole
    documents and the query is the verbatim phrase, so this is a phrase lookup: it
    measures whether a long document still ranks when its one matching passage is deep
    inside it, not semantic or passage search.
  - `manifest.json`: seed, options, counts per type for each gold file, pages per
    document, the scanned pages per document, the queries as
    `{query_id, doc_id, answer_page, answer_phrase}`, and the synthetic caveat, worded
    as in `generate_ground_truth.py`.
- **Personal data is synthetic and cannot be anyone's:**
  - names from the existing fictional lists, including names with particles
    ("van der", "de", "ter");
  - BSNs only from the **published test range 999990000–999999999** (Logius), still
    passing the elfproef;
  - IBANs on a bank code that does not exist (`ZZZZ`), still mod-97 valid;
  - telephone numbers, e-mail addresses, street addresses, postcodes and dates of
    birth, generated as in `wordsworth.eval.synthetic`.
- **Reproducible:** the same seed, options and environment give identical files. The
  scanned pixels come from pdfium's rasteriser (pypdfium2) and Pillow's encoder, so a
  different pypdfium2 or Pillow build may change their bytes. The gold of born-digital
  pages is read from the extracted text, so it follows the pdfium build too;
  `gold_scanned.jsonl` does not depend on pdfium.

## What the numbers mean

The PII score from this corpus comes from `pii_run` reading the gold text, not from
the pipeline reading the PDFs. The long-PDF form adds page-level localisation, the
scanned-page split and a real long corpus for `ingest_eval_corpus.py`; it does not
make the PII measurement end-to-end. That would be a separate change (detection over
the generated PDFs' extracted text).

## Out of scope

Committing a generated corpus to git (it is generated on demand). Changing the
detectors, `pii_run`, `run` or the metrics. Whole scanned documents and OCR. Uploading,
ingesting or indexing the corpus.
