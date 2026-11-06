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
    cover); default 0.1 = 3 pages of a 30-page document. Each chosen page is replaced
    by an image of itself, so it has no text layer. What this tests: such a document
    is still classified born-digital (`profile_pdf` counts characters per document),
    so it never reaches OCR and **those pages are lost without a trace**. It does not
    exercise OCR; whole scanned documents for OCR recovery are a later change.
  - `gold.jsonl`: **one line per born-digital page**, in exactly the format
    `wordsworth.eval.pii` `load_gold` reads, plus two keys it ignores:
    `{"id": "<doc-id>#p<NN>", "doc": "<doc-id>", "page": N, "text": "<that page's
    text>", "entities": [{"start", "end", "type"}]}`, offsets relative to the page's
    own text. Consequences, stated so a number is read right: `pii_run` reports
    `documents=<number of pages>` (about 900 for 30×30, minus scanned pages), and
    gold ids are not qrels ids: qrels use the PDF stem, the gold the page id, and the
    document is in the `doc` field.
  - `gold_scanned.jsonl`: the same records for the scanned pages, kept apart. They
    are **not** part of the score to quote: `pii_run` detects over gold text and never
    opens a PDF, so scoring them would count pages the pipeline cannot see as if
    extraction were perfect.
  - `queries.tsv` and `qrels.txt`: one query per document, whose only answer is a
    unique phrase planted on a page at or after page 20 (or the last page of a shorter
    document). Every document is judged for every query, non-relevant as 0, as the
    existing generator does. **What it is for:** long-document ranking fairness
    (`long-documents-rank-fairly`): a long document must still rank when its one
    matching passage is deep inside it. `wordsworth.eval.run` scores whole
    documents, so this measures exactly that, not passage search.
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
  scanned pages go through pdfium's renderer and Pillow's JPEG encoder, so a different
  pypdfium2 or Pillow build may change their bytes; the gold files are identical
  regardless.

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
