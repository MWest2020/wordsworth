---
status: draft
last_reviewed: 2026-07-12
---

# Architecture reference

Distilled from the [README](../../README.md) and the project brief. Migrated
without a content review, so this page is `draft`; a real review promotes it to
`current`.

## Pipeline

wordsworth is a single linear pipeline:

```
ingest → text extraction → anonymize/pseudonymize → store → index → hybrid search → rank
```

What a consumer does with the documents afterwards is out of scope — wordsworth
is the engine. Reference case: Woo-request handling for a Dutch municipality.

## Invariants

- **No clear PII toward the search index.** Anonymization is irreversible;
  pseudonymization is controlled and reversible and sits *before* indexing.
- **Append-only, hash-chained audit trail** over every transformation, from day
  one; PostgreSQL. No `UPDATE`/`DELETE` on audit records. The audit table is the
  document state machine — `documents.current_state` is derived from the latest
  audit record, never stored as a mutable column. There is no separate workflow
  engine.
- **A failed embedding is a hard error, never a silent fallback.** No silent
  fallbacks anywhere. A transport failure (the embedding service unreachable,
  timed out, a 5xx, a response cut off) is retried within the bounded retry
  budget first — with two Ollama instances the retry usually reaches the other
  one — and is a hard error after it. That holds for a document's embedding at
  ingest and for a query's (`hybrid_search`: `/hybrid`, console search, `/ask`).
  A bad embedding is never retried. Every retry is a JSON log line
  (`"event": "retry"`, and `"retry_exhausted"` when the budget runs out) naming
  what was retried and the exception's class, never its message: a message can
  quote the document.
- **No cloud APIs in the critical path.** Embeddings and any LLM run locally.
- **Driver/protocol pattern for every adapter** (anonymization, key/mapping
  store, object storage, search, embeddings).
- **Born-digital only for the PoC.** Scanned PDFs move to `unprocessable_ocr` in
  the audit trail; OCR is MVP-backlog.
- **Files ≤ 200 lines.**

## Stack

- Python 3.12+, managed with `uv` (never `pip`); FastAPI; pydantic v2.
- PostgreSQL. S3-compatible object storage (Ceph RGW target, SeaweedFS PoC).
- OpenSearch for BM25 (phase 3) and dense + hybrid/RRF (phase 4).
- Local inference: Ollama (bge-m3) for embeddings; GLiNER/Presidio via
  OpenAnonymiser for PII detection.

## Configuration

- **Secrets** via SOPS+age or OpenBao only — never hardcoded, never client-side,
  never a commercially licensed store.
- **License:** MIT. All code and dependencies must be license-compatible;
  AGPL is rejected where it would infect distribution.
- **Banned dependencies:** `anonypy`; MinIO (open-source edition deprecated
  April 2026 — use Ceph RGW or SeaweedFS behind the S3 seam); CyberArk/Conjur.

## Working on this

`uvx ruff check src/ tests/` before opening a PR. Deliberately narrow — `F` and
`E9`, real errors only, no style. A linter that argues about taste gets switched
off, and then it never catches the things it is for: its first run found a
protocol stub that had landed inside an implementation class and shadowed it,
and a test whose comment claimed a sanity check it did not make.

One token, one place that reads it: `pseudonymizer.label_of()`. The same
`[LABEL:hash]` parse used to live in four places, and a change to the token shape
would have found three of them.

## Reused components

- [OpenAnonymiser](https://github.com/ConductionNL/openanonymiser_light)
  (EUPL-1.2) — anonymization adapter (Presidio + GLiNER + deterministic regex;
  BSN elfproef, IBAN mod-97). EUPL is fine here precisely because it is reached
  over HTTP as a deployed service and never linked in: that is what keeps the
  MIT invariant intact.
- [zeef](https://github.com/MWest2020/zeef) (MIT) — ranking (local Ollama
  embeddings, cosine, UPGMA clustering, append-only audit-JSONL).
