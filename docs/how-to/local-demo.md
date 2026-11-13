---
status: current
last_reviewed: 2026-11-13
---

# The local demo: the console on synthetic data

One command serves the console on this machine, over a dossier of synthetic
letters, with no OpenSearch, Ollama, OpenBao, S3 or OpenAnonymiser anywhere. It
is for looking at a console page as a browser sees it, and for rehearsing the
demo script, without the cluster.

It proves **page behaviour**: what the console, the redacted PDF and a reveal do
with the data the pipeline produced. It does **not** prove detection quality or
ranking quality: the detector only knows the values the seed wrote, and the
embedder is a hash of the words. A good-looking result list here says nothing
about the real dossier.

## Start it

You need Postgres (role `wordsworth` may create databases) and `uv sync`.

```sh
psql postgresql://wordsworth:wordsworth@127.0.0.1/postgres -c 'CREATE DATABASE wordsworth_demo'
uv run python tools/demo/serve_local.py \
    --database-url postgresql+psycopg://wordsworth:wordsworth@127.0.0.1/wordsworth_demo \
    --port 8765 --reset
```

Seeding takes about ten seconds. It prints the counts, a key for `mark` and one
for `gast` (new on every start), the login URL, and the document the seeded
grant is for. Open `http://127.0.0.1:8765/console/login` and paste the `mark`
key. Ctrl-C stops it.

The command only runs on a database whose name starts with `wordsworth_demo`
or `wordsworth_test`, with or without `--reset`. It checks the name in the URL
(and refuses any `?query`, since `?dbname=` would connect elsewhere), and again
as `SELECT current_database()` reports it, before any schema work. `--reset`
drops and recreates every table; without it, the command refuses a database
that already holds documents (next section).

`create_app` reads its settings from `WORDSWORTH_*` environment variables
(identity provider, global grants, detection lists, rate limits). A variable
left in your shell would change what the demo shows, so the command removes
every `WORDSWORTH_*` variable from its own process and prints the names it
ignored. Run it from a clean shell anyway.

## What is real and what is a stand-in

| Part | In the demo |
|---|---|
| Postgres, schema (`init_schema`), audit trail, dossiers, topics, grants, key vault, mapping store, box maps | real, in your database |
| Pipeline: `ingest`, `process`, `delete_document`, `supersede`, `topics.compute`, `issue_grant` | real: every row was written by the function production calls |
| Redacted PDF and reveal PDF (pypdfium2 + reportlab) | real |
| Console, API, login, the corpus-read and grant-issue checks | real `create_app`, reversible mode |
| Search index | `InMemoryIndex` (term overlap + cosine), in the process |
| Embeddings | `DeterministicEmbedder` (a hash of the words) |
| Generator (`/ask`) | `DeterministicGenerator` (echoes, cites every source) |
| Object store (originals) | `InMemoryObjectStore`, in the process |
| OpenBao transit key | `FakeTransit`: a fixed KEK published in the source, so anything wrapped under it is readable by anyone. The data keys are real and wrapped under it in the Postgres key vault. Acceptable only for synthetic data in a demo database. |
| Entity detection (names, addresses) | a list of the values the seed wrote; BSN, IBAN, e-mail and postcode go through the real deterministic detectors |
| `POST /ingest` | refused with 403 before any route runs, for every caller: the stand-in detector knows only seeded names, so a real document would reach the index unredacted. No row and no stored original is created. |

Because the index and the object store live in the process, a restart loses
them while the database keeps its rows. A dossier whose searches find nothing
and whose PDFs are missing would look like a bug in the console, so the command
refuses such a database instead of serving it. Start with `--reset`.

## What is seeded

All of it from `wordsworth.eval.synthetic`, seed 20261113. Each letter's first
line reads "SYNTHETISCH DEMODOCUMENT"; the BSNs pass the elfproef and belong to
nobody, the IBANs are on a test bank code, the names come from a fixed list.

- One dossier, **Demo-dossier (synthetisch)**: 30 letters on six subjects
  (parkeren, afval, bouwen, subsidie, bezwaar, wmo), rendered to one-page PDFs
  with a real text layer, so every live letter has a box map.
- `demo-029` and `demo-030` deleted with `delete_document`.
- A scanned copy of `demo-001` (no text layer, `unprocessable_ocr`) superseded by
  `demo-001`, the way OCR recovery retires a scan.
- Topics computed over the dossier (six, one per subject).
- One grant: `mark` may reveal PERSON and BSN on `demo-007`.

That is 31 document rows: 28 live, 2 deleted, 1 superseded.

Callers: `mark` reads the corpus and issues grants; `gast` is logged in and is
refused both, which shows the "geen toegang" page.

## A walk with curl

```sh
B=http://127.0.0.1:8765
curl -s -c jar -o /dev/null -w '%{http_code}\n' --data-urlencode "key=<mark key>" $B/console/login   # 303
curl -s -b jar -H 'Accept: text/html' -o /dev/null -w '%{http_code}\n' $B/console                  # 200, or 303 to the dossier page
curl -s -b jar -H 'Accept: text/html' -G $B/console/search \
     --data-urlencode 'q=Wanneer krijg ik als bewoner een parkeervergunning?' --data-urlencode dossier=alle
curl -s -b jar $B/documents/<id>/redacted.pdf | head -c 5                                            # %PDF-
curl -s -b jar -H 'Content-Type: application/json' $B/documents/<id>/reveal \
     -d '{"grant_id": "<grant>", "types": ["PERSON"]}'
```

The grant id is on the document page (`data-grant`); the reveal adds a row to
the trail on that page.

## Adding to the seed

A later console change adds its own file under `tools/demo/seeds/` and one
call in `tools/demo/seeds/__init__.py`; the existing seeds stay as they are.
`tests/test_demo_harness.py` pins the counts above.
