# synthetic-long-corpus

## Why

Mark, 2026-11-06: "kunnen we ook een eval-dataset genereren voor testen? 30
documenten met 30 pagina's of zo."

The existing generator (`scripts/eval/generate_ground_truth.py`) writes ~500
*short text* documents. Real Woo publications are long PDFs: covers, e-mail
threads, minutes, tables, page headers and footers, and scanned pages. The things
that break on real dossiers (OCR, page boundaries, long-document ranking, redaction
boxes on page 27, a name that only appears in a footer) are exactly what a short-text
corpus cannot test.

## What changes

- **`scripts/eval/generate_long_corpus.py <outdir> --docs 30 --pages 30 --seed N
  [--scanned 0.1]`** writes:
  - `documents/<doc-id>.pdf`: born-digital PDFs of about `--pages` pages each, built
    from realistic Woo parts (a cover page, a table of contents, letters, e-mail
    threads, minutes, tables), with page headers and footers ("pagina x van y", a
    document number) and the footer marking `SYNTHETISCH` on every page.
  - a fraction of pages (`--scanned`, default 0.1) rendered to an image and put back
    as image-only pages, so OCR is exercised.
  - `gold.jsonl`: every planted value with doc id, page number (1-based), type and
    value, in the format `wordsworth.eval.pii_run` reads, extended with `page`.
  - `queries.tsv` and `qrels.txt`: at least one query per document whose answer sits on
    page 20 or later, for `wordsworth.eval.run`.
  - `manifest.json`: seed, counts per type, pages per document, scanned pages, and the
    caveat that this text is more regular than administrative reality.
- **Personal data is synthetic and cannot be anyone's:**
  - names from the existing fictional lists, including names with particles
    ("van der", "de", "ter");
  - BSNs only from the test range starting `9999`, still passing the elfproef;
  - IBANs on a bank code that does not exist;
  - telephone numbers, e-mail addresses, street addresses, postcodes and dates of
    birth, generated the same way as in `wordsworth.eval.synthetic`.
- The same seed gives byte-for-byte the same corpus.

## Out of scope

Committing a generated corpus to git (it is generated on demand). Changing the
detectors or the evaluation metrics. Uploading the corpus anywhere.
