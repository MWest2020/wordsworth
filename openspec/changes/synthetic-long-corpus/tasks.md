# Tasks

## 1. Values
- [x] `bsn_test_range(rng)` (in 999990000–999999999, passes the elfproef) and
      `iban_fake_bank(rng)` (bank code `ZZZZ`, mod-97 valid) in
      `wordsworth.eval.synthetic`, next to the existing `bsn` and `iban`; the comment
      on `iban()` no longer calls INGB a test bank. Proved by: tests that the values are
      in range, pass `is_valid_bsn` / `is_valid_iban`, and that `bsn`/`iban` outputs for
      a fixed seed are unchanged.
## 2. Generator
- [x] `long_corpus.py`, `long_corpus_pdf.py` and the thin CLI
      `scripts/eval/generate_long_corpus.py` write `documents/*.pdf`, `gold.jsonl`,
      `gold_scanned.jsonl`, `queries.tsv`, `qrels.txt` and `manifest.json` as in the
      proposal. Proved by: a test that generates `--docs 2 --pages 6` into a tmp dir and
      checks the files, the page counts, the header/footer (`pagina x van y`, the
      `WOO-` number) and `SYNTHETISCH` on every page's extracted text.
- [x] Gold is true. `load_gold` accepts `gold.jsonl` and `gold_scanned.jsonl`; every gold
      value of a born-digital page appears in that page's `page_text`; every scanned page
      has an empty text layer, appears in `gold_scanned.jsonl` and not in `gold.jsonl`;
      page 1 is never scanned. Proved by: tests over the small corpus.
- [x] No unplanned BSN or postcode. `find_deterministic` over every born-digital page
      finds no BSN or postcode that is not in that page's gold. Proved by: a test.
- [x] Queries. The manifest lists one query per document with `answer_page` ≥ 20, or
      the last page of a shorter document; the answer phrase is on that page's extracted
      text and in no other document; `load_queries` and `load_qrels` parse the files; qrels
      judge every document for every query. Proved by: a test. Use `--pages 22` for the
      ≥ 20 case.
- [x] Reproducible. Two generations with the same seed and options into different
      directories give identical files, and the PDFs' creation date is the invariant
      constant. Proved by: a test.
## 3. Docs and the real run
- [x] `scripts/eval/README.md` (Dutch, like the rest of it): generating the long corpus,
      `pii_run` over `gold.jsonl` (the number to quote), why `gold_scanned.jsonl` is not
      quoted, and `run` over `queries.tsv`/`qrels.txt`.
- [x] Run the real thing once: `generate_long_corpus.py` on 30×30, note the wall-clock
      and the size on disk in the step's log entry, and run `python -m
      wordsworth.eval.pii_run` over its `gold.jsonl` (deterministic layers).
      `uv run ruff check src/ tests/` and the full suite pass.

      Run log (seed 20261106, `--docs 30 --pages 30 --scanned 0.1`, this
      environment): generation took 10.5 s wall-clock and the output directory
      is 11.4 MB on disk (30 PDFs, ~90 rasterised pages at 200 dpi).
      `python -m wordsworth.eval.pii_run gold.jsonl --layers deterministic`
      reported `documents=810` (900 pages minus the 90 scanned, as predicted)
      and span P=1.000 R=1.000 on BSN/IBAN/EMAIL/POSTCODE; PERSON/LOCATION/
      PHONE_NUMBER are gold for the openanonymiser layer and score R=0.000
      with the deterministic layer alone, as expected. `uv run ruff check
      src/ tests/` and the full suite (1335 passed, 13 skipped — all
      unrelated service/Docker skips) are clean.
