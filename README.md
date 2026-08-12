# wordsworth

A sovereign pipeline that turns large volumes of (mostly Dutch) government
documents into a searchable, privacy-safe corpus:

**ingest → text extraction → anonymize/pseudonymize → store → index → hybrid search → rank**

What a consumer does with the documents afterwards is out of scope — wordsworth
is the engine. Reference case: Woo-request handling for a Dutch municipality.

## Principles

- Boring and auditable over fast or clever.
- No PII in the search index. Anonymization is irreversible; pseudonymization is
  controlled and reversible, and sits *before* indexing.
- Append-only, tamper-evident audit trail over every transformation, from day one.
- Local inference only — embeddings and any LLM run locally; no cloud APIs in the
  critical path.
- A failed embedding is a hard error, never a silent fallback.

## Status

Proof-of-concept, under construction. PoC scope: ingest + extraction +
anonymization, one corpus indexed and searchable via API with a closing audit
trail. Design and delta specs live under `openspec/`.

## Usage

Deploy with the manifests + runbook under [`deploy/`](deploy/README.md). Once the
API is running it serves interactive docs at `/docs` (Swagger) and `/redoc`.

### CLI (`wordsworth`)

A dependency-free client for the HTTP API (`src/wordsworth/client.py` — stdlib
only, so it runs anywhere with Python 3, no install of the package needed).

```bash
# put it on PATH as `wordsworth` (saves the API URL to config; env/--url override)
scripts/install-cli.sh --url http://100.100.181.23:8000

# or set/inspect the persistent config yourself
wordsworth config --url http://100.100.181.23:8000   # ~/.config/wordsworth/config.yaml
wordsworth config --show

wordsworth health                                   # {"status": "ok"}
wordsworth ingest ./corpus                           # a PDF file or a directory
wordsworth ingest ./corpus --batch 5                 # smaller batches (slow CPU)
wordsworth ingest ./corpus --all                     # upload every file, not just *.pdf
wordsworth search "vergunning"                       # BM25
wordsworth hybrid "vergunning"                       # BM25 + vector (relevance)
wordsworth ask "wat zijn de kosten?"                 # RAG answer via the local LLM
wordsworth state <document-id>                       # current pipeline state
wordsworth meta <document-id>                        # duration, PII counts, step trail
```

Without the install step, point at the API per call or via the environment:

```bash
wordsworth --url http://100.100.181.23:8000 ingest ./corpus
# or
export WORDSWORTH_API_URL=http://100.100.181.23:8000
wordsworth ingest ./corpus
```

`ingest` walks a directory recursively (`*.pdf`, or `--all`) and uploads to
`POST /ingest` in batches, printing a per-file result and an `X/Y indexed`
summary. A file that fails does not abort the batch. See `wordsworth --help` and
[`docs/reference/cli.md`](docs/reference/cli.md).

## Reused components

- [OpenAnonymiser](https://github.com/ConductionNL/openanonymiser_light) — anonymization adapter.
- [zeef](https://github.com/MWest2020/zeef) — ranking component (local Ollama embeddings, cosine).

## License

EUPL-1.2 — see [LICENSE](LICENSE).
