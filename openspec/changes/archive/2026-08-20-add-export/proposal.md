## Why

Fase A: operators need to take the work out of the system — a downloadable ZIP of
the de-identified documents, and a CSV of a ranking — to review, share, or feed a
future UI. Today the corpus is only reachable through the read/search endpoints.

## What Changes

- **`GET /export/anonymized.zip`** — a ZIP whose entries are `{document_id}.txt`
  holding each INDEXED document's stored de-identified text; an optional
  `?document_ids=a,b,c` filters to a subset. Only the index-bound anonymized text
  is written — never clear PII, never original bytes; documents without stored
  text are skipped.
- **`GET /export/ranking.csv?query=&k=`** — the lexical ranking for a query as CSV
  (Excel-openable), one row per hit: `rank,document_id,score,object_key`. Reuses
  the existing search path; de-identified metadata only.
- **CLI `wordsworth export docs <out.zip>`** and **`wordsworth export ranking
  "<query>" <out.csv>`** (stdlib-only) download and save those exports.

## Capabilities

### Added Capabilities
- `export`: download the de-identified corpus as a ZIP and a query ranking as CSV,
  via API and CLI, containing only de-identified content.

## Impact

- Code: `api.py` (two routes + pure `_ranking_csv`/`_anonymized_zip`/`_indexed_texts`
  helpers), `client.py` (`export` subcommands + a `_download` helper). Stdlib only
  (`zipfile`, `csv`) — no new dependency.
- The ZIP route mounts with the DB (session), the CSV route with the search index —
  each under the dependency it needs, like the other routes.
- Tests: pure (zip/csv helpers + ranking endpoint) and DB-integration (zip over a
  real DB, filter, skip-non-indexed) + CLI download tests.
