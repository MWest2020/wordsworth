# CLAUDE.md — wordsworth contract

This file is the single contract. Every agent reads it. The **reviewer** and
**security** agents test a change against **this file + the change only** —
never against anything else. If a rule matters, it lives here, literally.

> SKELETON — Mark sharpens this. Values below are transcribed from the project
> brief; edit here, not in the agents.

## What wordsworth is

A sovereign pipeline turning large volumes of (mostly Dutch) government
documents into a searchable, privacy-safe corpus:

`ingest → text extraction → anonymize/pseudonymize → store → index → hybrid search → rank`

What a consumer does with the documents afterwards is out of scope. Boring and
auditable beats fast or clever — always name the "clever pitfall" when relevant.

## Hard constraints (invariants — non-negotiable)

- **EUPL-1.2.** All code and dependencies must be license-compatible. Reject
  AGPL where it would infect distribution (e.g. PyMuPDF — use pypdf/pdfminer).
- **No clear PII toward the search index.** Anonymization is irreversible;
  pseudonymization is controlled and reversible and sits *before* indexing.
- **Mutable audit tables do not exist.** The audit trail is append-only and
  hash-chained; PostgreSQL from day one. No UPDATE/DELETE on audit records.
- **A failed embedding is a hard error, never a silent fallback** (null-vector
  rule). The same principle applies broadly: no silent fallbacks.
- **No cloud APIs in the critical path.** Embeddings and any LLM run locally.
  Claude as a *build* agent is not the pipeline runtime — keep that distinction.
- **Secrets** via SOPS+age or OpenBao only. Never commercially licensed, never
  client-side, never hardcoded.
- **Banned dependencies:** `anonypy` (never); `MinIO` (open-source edition
  deprecated April 2026 — use Ceph RGW or SeaweedFS behind the S3 seam);
  CyberArk/Conjur. NiFi is not a given.

## Architecture invariants

- **The append-only audit table is the document state machine is the
  orchestration state.** No workflow engine. Every step transition is an audit
  record. `documents.current_state` is *derived* from the latest audit record,
  never stored as a mutable column.
- **Driver/protocol pattern for every adapter** (anonymization, key/mapping
  store, object storage, search, embeddings).
- **Born-digital only for the PoC.** Scanned PDFs → status `unprocessable_ocr`
  in the audit trail. OCR is MVP-backlog.
- **Files ≤ 200 lines.**

## Stack

- Python 3.12+ managed with **`uv`** (never `pip`), FastAPI, pydantic v2.
- PostgreSQL. S3-compatible object storage (Ceph RGW target / SeaweedFS PoC).
- OpenSearch for BM25 (phase 3) and dense+hybrid/RRF (phase 4).
- Local inference: Ollama (bge-m3) for embeddings; GLiNER/Presidio via
  OpenAnonymiser for PII.

## Reused components (reuse, do not rebuild)

- **OpenAnonymiser** (`ConductionNL/openanonymiser_light`, EUPL-1.2) —
  anonymization adapter (Presidio + GLiNER + deterministic regex; BSN elfproef,
  IBAN mod-97).
- **zeef** (`MWest2020/zeef`, EUPL-1.2) — ranking (local Ollama embeddings,
  cosine, UPGMA clustering, append-only audit-JSONL). clustering ≠ ranking;
  reach ≠ relevance; `--no-llm` + cosine is the proven path.

## Working method & governance

- Work follows OpenSpec: propose → apply → archive. One builder run implements
  exactly one change, nothing outside it. "Done = green" (tests pass).
- **Merges belong to Mark** (Habitat v0 rule). `main` is protected.
- `CLAUDE.md`, `.claude/agents/`, and CI config are owned by Mark (CODEOWNERS).
  Agents must never modify them — the reviewer hard-fails any diff that does.
