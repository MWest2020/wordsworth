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
  fallbacks anywhere.
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
- **License:** EUPL-1.2. All code and dependencies must be license-compatible;
  AGPL is rejected where it would infect distribution.
- **Banned dependencies:** `anonypy`; MinIO (open-source edition deprecated
  April 2026 — use Ceph RGW or SeaweedFS behind the S3 seam); CyberArk/Conjur.

## Reused components

- [OpenAnonymiser](https://github.com/ConductionNL/openanonymiser_light)
  (EUPL-1.2) — anonymization adapter (Presidio + GLiNER + deterministic regex;
  BSN elfproef, IBAN mod-97).
- [zeef](https://github.com/MWest2020/zeef) (EUPL-1.2) — ranking (local Ollama
  embeddings, cosine, UPGMA clustering, append-only audit-JSONL).
