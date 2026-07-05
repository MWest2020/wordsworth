# Change: add-pipeline-skeleton

## Why

wordsworth needs a spine before it needs search. Every document that enters
the pipeline moves through a sequence of transformations, and the 10-year
audit requirement means *every* transition must be recorded, append-only and
tamper-evident, from day one. That same record is the orchestration state:
we do not need a workflow engine, we need one append-only table that is at
once the audit trail and the per-document state machine.

Two corpus unknowns (born-digital share, document size) must not block the
build. Instead the pipeline measures them itself: a cheap, deterministic
born-digital detection step classifies each document and records the raw
metric, so the run report falls out of the audit data rather than out of a
pre-run assumption.

## What Changes

- **PostgreSQL as authoritative store, day one.** One append-only audit table
  that doubles as the document state machine. No mutable rows.
- **Global hash-chained audit trail.** Each transition record links to its
  predecessor by `sha256(prev_hash ‖ canonical(record))`. Single global chain,
  trivially verifiable.
- **Document state machine** with atomic transition-plus-audit writes, making
  the pipeline idempotent and resumable after a crash.
- **Born-digital detection as real logic** (pypdf, BSD): counts extractable
  characters per page, classifies `extractable` vs `unprocessable_ocr`, records
  the raw metric. A parser crash is `failed`, never a silent OCR fallback.
- **Stub transitions** for `extract`, `anonymize`, `index` — the states and
  audit records exist; the real work arrives in changes (c), (b), (d).
- **JSONL export** as a derived, append-only view of the audit table (same
  records, same hashes) for the later WORM/object-lock export path.

## Capabilities

### New Capabilities
- `document-lifecycle`: the per-document state machine, its transitions, born-digital
  detection, and the stub transitions that later changes fill in.
- `audit-trail`: the append-only, hash-chained PostgreSQL audit store (also the
  orchestration state) and its derived JSONL export.

### Modified Capabilities
<!-- none: first change, no existing specs -->

## Impact

- New dependency: `pypdf` (BSD). Rejected: PyMuPDF (AGPL — copyleft risk in a
  sovereign EUPL-1.2 tool delivered to municipalities).
- New dependency surface: PostgreSQL + a migration tool; FastAPI skeleton only.
- No search code, no OpenSearch, no embeddings. Those are changes (d) and later.
- Establishes the driver/protocol seam that (c) and (b) plug into.
- `documents.current_state` is DERIVED from the latest audit record, not stored —
  keeping the audit table the single source of truth (per session decision).
