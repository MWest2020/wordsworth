# Tasks

## 1. Values
- [ ] `bsn_test_range(rng)` (starts with `9999`, passes the elfproef) and
      `iban_fake_bank(rng)` (mod-97 valid, bank code that does not exist) in
      `wordsworth.eval.synthetic`. Proved by: tests for range, elfproef and mod-97.
## 2. Generator
- [ ] `scripts/eval/generate_long_corpus.py` writes `documents/*.pdf`, `gold.jsonl`
      (with `page`), `queries.tsv`, `qrels.txt` and `manifest.json` as in the
      proposal; the `SYNTHETISCH` footer is on every page. Proved by: a test that
      generates a small corpus (`--docs 2 --pages 6`) and checks the files, the page
      counts and the footer.
- [ ] Every gold value is on its page in the extracted text of born-digital pages, and
      scanned pages have no text layer. Proved by: a test over the small corpus.
- [ ] The same seed gives identical files. Proved by: a test that generates twice and
      compares hashes.
- [ ] At least one query per document has its answer on page 20 or later in a 30-page
      corpus. Proved by: a test on the qrels and gold.
## 3. Docs
- [ ] `scripts/eval/README.md`: how to generate the long corpus and run `pii_run` and
      `run` over it. `uv run ruff check src/ tests/` and the full suite pass.
