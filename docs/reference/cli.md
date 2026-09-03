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

## Examples

```bash
# one-off, explicit URL
wordsworth --url http://100.100.181.23:8000 health

# ingest a corpus directory in small batches
wordsworth --url http://100.100.181.23:8000 ingest /data/corpus --batch 5

# search and inspect
wordsworth search "vergunning" --size 5
wordsworth state 66c86e91-830f-4ed7-99cf-ac4407d262fb
```

See also the live, interactive API docs at `/docs` (Swagger) and `/redoc` on a
running instance.
