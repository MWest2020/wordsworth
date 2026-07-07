# Tasks — add-pipeline-skeleton

Done = green: every task ships with its tests in the same builder run.

## 1. Project & database
- [x] 1.1 uv project deps: `pypdf`, `psycopg`/SQLAlchemy, `pydantic` v2, `fastapi` (skeleton only)
- [x] 1.2 PostgreSQL migration: append-only `audit_records` table with `seq`,
      `document_id`, `from_state`, `to_state`, `ts`, `step`, `payload`,
      `prev_hash`, `hash`; no UPDATE/DELETE grant
- [x] 1.3 `documents` table (id, object-storage key) — `current_state` is DERIVED
      from the latest audit record, NOT stored (audit table = single source of truth)

## 2. Audit trail
- [x] 2.1 Canonical JSON serialization for records (stable key order)
- [x] 2.2 Hash-chain append: read tail `hash`, compute new `hash`, insert
- [x] 2.3 Chain verifier: walk records, recompute, report first mismatch
- [x] 2.4 Derived JSONL exporter (same records + hashes)
- [x] 2.5 Tests: append links correctly; tamper is detected; export mirrors table

## 3. State machine
- [x] 3.1 State enum + allowed-edges map
- [x] 3.2 `transition(document, to_state, step, payload)` — one transaction:
      guard edge, write audit record, advance state; no-op if already past
- [x] 3.3 Tests: undefined edge rejected; atomicity (no partial on crash);
      idempotent resume

## 4. Born-digital detection
- [x] 4.1 pypdf profiler: count extractable chars over all pages → chars, pages, bytes
- [x] 4.2 Classify against configurable threshold `T` → `extractable` /
      `unprocessable_ocr`; record raw metric in payload
- [x] 4.3 Parser exception → `failed(reason)`, never `unprocessable_ocr`
- [x] 4.4 Tests: born-digital → extractable; scanned → unprocessable_ocr;
      crash → failed; raw metric present in payload

## 5. Stub transitions
- [x] 5.1 `extract`, `anonymize`, `index` stubs: advance state + audit record,
      no domain work
- [x] 5.2 Tests: stub advances state and writes audit, performs no transform

## 6. End-to-end
- [x] 6.1 Ingest a small fixture set (born-digital + scanned + corrupt) and run
      the pipeline to `indexed` / `unprocessable_ocr` / `failed`
- [x] 6.2 Verify chain integrity end-to-end; emit a run report (counts per
      terminal state, born-digital share, size distribution)
