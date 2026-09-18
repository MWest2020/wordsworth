---
status: draft
last_reviewed: 2026-09-03
---

# CLI reference — `wordsworth`

`wordsworth` (alias `wordsworthctl`) is a dependency-free client for the
Wordsworth HTTP API. It lives in `src/wordsworth/client.py` and uses only the
Python 3 standard library, so it runs on any machine with Python 3 — you do not
need to install the `wordsworth` package or its dependencies. This makes it the
tool of choice on a machine that only reaches the API over the network (e.g. to
ingest a corpus).

## Install

Put it on `PATH` as `wordsworth` (and `wordsworthctl`):

```bash
scripts/install-cli.sh [--url <api-base-url>] [--bin-dir <dir>]
```

- `--url` bakes a default API base URL into the installed copy, so
  `wordsworth health` works with zero configuration. The `WORDSWORTH_API_URL`
  environment variable still overrides it.
- `--bin-dir` defaults to `~/.local/bin` (ensure it is on your `PATH`).

No package install is required — the script just copies the single stdlib file.
If the `wordsworth` package *is* installed (`uv sync` / `pip install`), the
`wordsworth` and `wordsworthctl` console scripts are provided too.

## Configuration

Set the API URL once, persistently, so you don't repeat `--url`:

```bash
wordsworth config --url http://100.100.181.23:8000    # also --batch, --timeout
wordsworth config --show                              # print current config
```

This writes `~/.config/wordsworth/config.yaml` (override the path with
`$WORDSWORTH_CONFIG`) — a flat `key: value` file (`url`, `batch`, `timeout`),
parsed with the standard library (so still no dependencies; it is a small YAML
subset, not full YAML). `install-cli.sh --url` writes it for you.

The API base URL is resolved in this order:

1. `--url <url>` on the command line
2. `$WORDSWORTH_API_URL`
3. `url` in the config file
4. built-in default `http://localhost:8000`

`--batch` / `--timeout` resolve as: flag → config file → built-in default.

## Commands

| Command | Description |
| --- | --- |
| `wordsworth health` | Check the API is up (`GET /health`). |
| `wordsworth ingest <path>` | Upload a PDF file, or every PDF under a directory, to `POST /ingest`. |
| `wordsworth search <query> [--size N]` | Lexical (BM25) search (`GET /search`). |
| `wordsworth hybrid <query> [--size N]` | Hybrid BM25 + vector relevance search (`GET /hybrid`). |
| `wordsworth ask <query> [--k N]` | RAG answer with citations via the local LLM (`GET /ask`). |
| `wordsworth state <document-id>` | Pipeline state of a document (`GET /documents/{id}/state`). |
| `wordsworth meta <document-id>` | Full metadata: duration, PII counts, step trail (`GET /documents/{id}`). |
| `wordsworth config [--url … --batch … --timeout …] [--show]` | Show or set persistent defaults. |

### `ingest`

```bash
wordsworth ingest <file-or-directory> [--all] [--batch N] [--timeout SECONDS]
```

- Walks a directory **recursively**; by default only `*.pdf`, or `--all` for
  every file.
- Uploads in batches of `--batch` files per request (default 25). On slow
  (CPU-only) deployments use a smaller batch, e.g. `--batch 5` or `--batch 1`, so
  each request stays short.
- Prints a per-file line — `filename: state`, with the processing duration and
  non-zero PII counts on success (e.g. `2130276.pdf: indexed (1.8s, bsn=1
  person=2)`), or the error class on failure — and a final `X/Y indexed, Z failed`
  summary. A file that fails does **not** abort the batch. Exit code is non-zero
  if any file failed.
- The pipeline is **PDF-only**; non-PDF files come back as `error`.

## `wordsworth-dossier-uit-herkomst` and `wordsworth-dossier-hernoem`

Correcting a classification, without guessing.

```bash
wordsworth-dossier-uit-herkomst herkomst.jsonl --weg-uit "corpus-2026-09" --dry-run
wordsworth-dossier-hernoem "corpus-2026-09" "Gooise Meren Woo-publicatie 2022"
```

`uit-herkomst` puts each document into the dossier its **recorded provenance**
names — `scripts/eval/fetch_woo_corpus.py` writes one line per document with the
source URL and the decision it belongs to. A document with no provenance entry is
**not assigned** and is counted. A classification derived from a date or a text
pattern is one nobody can retell afterwards, and that is worse than none.

`--weg-uit` removes them from a dossier they were wrongly placed in, once they
are somewhere else. If that leaves documents belonging nowhere at all, the count
is reported — such a document is invisible to every scoped search, and the moment
it happens is the moment someone can still act on it.

`hernoem` moves no document: the identity is the dossier, not the word used for
it.

The provenance file may contain duplicate lines — the fetcher opens it with
`append`, so running it twice duplicates every entry. Both commands key on the
filename, so that is harmless; it is only a reason not to count lines.

## `wordsworth-access-preflight`

Reports the grants that go inert once callers are identities instead of key
labels, and changes nothing.

```bash
wordsworth-access-preflight
```

A grant names who may reveal and the caller must be that recipient. A recipient
that is a key label stops matching anybody the moment callers are people. Run
this **before** switching, not after — see
[access identity](../how-to/access-identity.md).

## `wordsworth-backfill-dossier`

Places documents that predate dossiers into one named dossier, so a scoped search
can still reach them.

```bash
wordsworth-backfill-dossier "corpus-2026-09" --dry-run
wordsworth-backfill-dossier "corpus-2026-09"
```

A scoped search answers only from the dossiers in scope, so documents belonging
to none are invisible — and every document ingested before dossiers existed
belongs to none. A scope that makes the existing corpus unfindable is not a
migration but a loss.

Name them for where they came from rather than pretending they were a case. They
arrived as one corpus, in one go.

It also **updates the index**, because the index holds the dossiers per document:
a membership the index does not know about is a document a scoped search still
cannot reach, and then the command would not have done the one thing it exists
for. `--no-index` skips that and says plainly that a reindex stays due.

`--dry-run` does **not** touch the index. The database can be rolled back; the
index cannot. The first dry run against production wrote 770 documents before
this was fixed, which made "dry" a lie.

Run it **after** deploying the new code, not before: in between, the existing
documents are in no dossier while the new code already requires a scope.

## `wordsworth-backfill-filenames`

Gives existing documents back the name their file arrived under, by content hash.

```bash
wordsworth-backfill-filenames /data/corpus --dry-run
wordsworth-backfill-filenames /data/corpus
```

Ingestion has always been content-addressed (`documents/<sha256>`) — the right
identity, and unreadable. Documents ingested before the `filename` column existed
have no name in the database, but the bytes on disk still do, and the hash is the
bridge.

It does not guess. A document whose bytes are not in the directory keeps no name,
and the console then says `naamloos (<first 8 of the hash>)` rather than printing
a hash where a name belongs. A name already recorded is kept — that one came from
the caller at ingest time, which beats a file that happens to sit in a directory
today; `--overwrite` says otherwise.

Reports four numbers: named, kept, documents without a file, files without a
document.

## `wordsworth-measure-combinations`

Counts, per declared combination, in how many documents **every** type occurs.
Measure before claiming: without this number, any statement about quasi-
identifiers in a corpus is a guess.

```bash
wordsworth-measure-combinations profiles/example-wi.json
```

It accepts a profile (it reads the `combinations` block) or a bare JSON list of
`{types, reason}` declarations. Output is one line per combination:

```
    12  BSN + POSTCODE
     0  DATE + GENDER + POSTCODE  [unobservable: DATE, GENDER]
```

Two things to read carefully.

The count comes from the pseudonyms the pipeline **minted** per document
(`document_pseudonyms`), not from re-running the detectors over the source text.
That makes it a statement about what the pipeline did, on the text it saw.

`unobservable` names types the corpus carries nowhere, because the pipeline has
no detector for them. "Does not occur" and "cannot be seen" are different
answers, and a bare zero gives the reassuring one.

Exit code 2 if the file declares no combinations.

## Examples

```bash
# one-off, explicit URL
wordsworth --url http://100.100.181.23:8000 health

# ingest a corpus directory in small batches
wordsworth --url http://100.100.181.23:8000 ingest /data/corpus --batch 5

# search and inspect
wordsworth search "vergunning" --dossier zaak-a --size 5
wordsworth state 66c86e91-830f-4ed7-99cf-ac4407d262fb

# how often does a declared combination actually occur?
wordsworth-measure-combinations profiles/example-wi.json
```

See also the live, interactive API docs at `/docs` (Swagger) and `/redoc` on a
running instance.
