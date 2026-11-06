# Tasks

## 1. Values
- [ ] `bsn_test_range(rng)` (in 999990000–999999999, passes the elfproef) and
      `iban_fake_bank(rng)` (bank code `ZZZZ`, mod-97 valid) in
      `wordsworth.eval.synthetic`, next to the existing `bsn` and `iban`; the comment
      on `iban()` no longer calls INGB a test bank. Proved by: tests that the values are
      in range, pass `is_valid_bsn` / `is_valid_iban`, and that `bsn`/`iban` outputs for
      a fixed seed are unchanged.
## 2. Generator
- [ ] `long_corpus.py` (page assembly, per-page gold, queries), `long_corpus_parts.py`
      (the six part builders), `long_corpus_pdf.py` and the thin CLI
      `scripts/eval/generate_long_corpus.py` write `documents/*.pdf`, `gold.jsonl`,
      `gold_scanned.jsonl`, `queries.tsv`, `qrels.txt` and `manifest.json` as in the
      proposal. Proved by: a test that generates `--docs 2 --pages 6` into a tmp dir and
      checks the files, the page counts, the header/footer (`pagina x van y`, the
      `WOO-` number) and `SYNTHETISCH` on every page's extracted text.
- [ ] Gold `text` is the page's extracted text. For a born-digital page the gold `text`
      is `page_text` of that page, and each offset is computed by locating the gold value
      in it; every value must be found exactly once, otherwise the generator fails.
      Proved by: a test that `load_gold` accepts every record of the small corpus (range
      check holds), that per page the gold `text` equals `page_text` of the PDF page, and
      that every entity's slice of `text` equals its planted value and occurs once.
- [ ] Gold is true. `load_gold` accepts `gold.jsonl` and `gold_scanned.jsonl`; every gold
      value of a born-digital page is found exactly once in that page's `page_text`; every
      scanned page has an empty text layer, appears in `gold_scanned.jsonl` and not in
      `gold.jsonl`; page 1 is never scanned. Proved by: tests over the small corpus,
      generated with an explicit `--scanned 0.5` on `--docs 2 --pages 6`, which also
      assert that at least one scanned page exists, so no scanned-page assertion passes
      vacuously.
- [ ] The answer page is never scanned. Scanned pages are drawn from the pages other
      than page 1 and the answer page, so the planted answer always has a text layer.
      Proved by: a gate test that, for every document of the generated corpus and over
      several seeds, asserts answer page ∉ scanned set (so the answer-phrase check in
      the queries task is not seed-flaky).
- [ ] Every file stays ≤ 200 lines. Proved by: a test (or the CI check) that counts the
      lines of `long_corpus.py`, `long_corpus_parts.py`, `long_corpus_pdf.py`,
      `synthetic.py` and `scripts/eval/generate_long_corpus.py`.
- [ ] Detections equal gold, exactly. `find_deterministic` over every born-digital page
      returns, for all four deterministic types (`bsn`, `iban`, `email`, `postcode`),
      exactly the spans in that page's gold of that type: nothing missing, nothing extra,
      not only BSN and postcode. The e-mail thread part plants every From/To address as
      gold, or uses addresses `_EMAIL_RE` does not match. Offsets are
      into the extracted text, which is the gold `text`, so this is offset-exact. Proved
      by: a test comparing, per page and per type, the detected `(type, start, end)` set
      over `page_text` with the pinned gold `(type, start, end)` set.
- [ ] Queries. The query text in `queries.tsv` is the planted phrase verbatim, equal to
      `answer_phrase` in the manifest. The manifest lists one query per document with
      `answer_page` ≥ 20, or the last page of a shorter document; the answer phrase is on that page's extracted
      text and in no other document; `load_queries` and `load_qrels` parse the files; qrels
      judge every document for every query. Proved by: a test. Use `--pages 22` for the
      ≥ 20 case.
- [ ] Every canvas is `Canvas(..., invariant=1)`, with Author, Title, Subject and
      Creator set explicitly. Proved by: a test that the PDFs' creation date is the
      invariant constant, and a check that no `Canvas(` in the generator modules lacks
      `invariant=1`.
- [ ] Scanned pixels come from pdfium: the chosen page is rasterised with pypdfium2 (as
      `pdf_render.py` does), encoded by PIL and re-embedded as an image-only PDF page in
      place of the text page. Proved by: the scanned-page tests over the small corpus
      (explicit `--scanned 0.5`, at least one scanned page asserted, empty text layer,
      page count unchanged, the page holds an image).
- [ ] Reproducible. Two generations with the same seed and options into different
      directories give byte-identical files. Proved by: a test comparing the bytes of
      every file.
## 3. Docs and the real run
- [ ] Document the generator for the docs drift gate. The gate (`gates / gates`) is
      path-based (code_paths `src/,scripts/`, drift_mode fail): PR #396 touched code
      there without touching `docs/` and was refused. Add
      `docs/reference/synthetic-long-corpus.md` with front matter `status` and
      `last_reviewed` (no `owner`), describing the generator, its options, its output
      files and the per-page gold format (`gold.jsonl` and `gold_scanned.jsonl`: `id`,
      `doc`, `page`, `text` (the page's extracted text, which the detectors scan; offsets into it, each value located exactly once),
      `entities`), that the queries are the planted phrase verbatim (a phrase lookup), and
      link it from `docs/index.md` under
      `reference/`. The same PR contains this docs change; no `docs-drift-ok` label,
      because this adds outward behaviour. Proved by: `gates / gates` green on the PR,
      the page's front matter has the two keys and no `owner`, and `docs/index.md`
      links to it.
- [ ] `scripts/eval/README.md` (Dutch, like the rest of it): generating the long corpus,
      `pii_run` over `gold.jsonl` (the number to quote), why `gold_scanned.jsonl` is not
      quoted, and `run` over `queries.tsv`/`qrels.txt`.
- [ ] Run the real thing once: `generate_long_corpus.py` on 30×30, note the wall-clock
      and the size on disk in the step's log entry, and run `python -m
      wordsworth.eval.pii_run` over its `gold.jsonl` (deterministic layers).
      `uv run ruff check src/ tests/` and the full suite pass.
