## 1. Export API

- [x] 1.1 `GET /export/anonymized.zip` — ZIP of `{id}.txt` de-identified texts for
  INDEXED docs; `?document_ids=` filter; skip docs without stored text.
- [x] 1.2 `GET /export/ranking.csv?query=&k=` — ranked CSV (rank/id/score/key).
- [x] 1.3 Pure helpers `_anonymized_zip`, `_ranking_csv`, `_indexed_texts`.

## 2. Export CLI

- [x] 2.1 `wordsworth export docs <out.zip>` and `export ranking "<q>" <out.csv>`
  (stdlib-only) via a `_download` helper.

## 3. Gate

- [x] 3.1 Local tests: zip/csv helpers, ranking endpoint, CLI download (no clear PII).
- [x] 3.2 DB-integration (CI): zip over a real DB, id-filter, skip-non-indexed.
- [x] 3.3 Full suite green in CI + `openspec validate`.
