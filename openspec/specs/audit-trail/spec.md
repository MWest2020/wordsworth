# audit-trail Specification

## Purpose
TBD - created by archiving change add-pipeline-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Append-only audit store

The audit trail SHALL live in PostgreSQL as the single source of truth and
SHALL be append-only: audit records are never updated or deleted. This store is
also the document orchestration state.

#### Scenario: No mutation path exists

- **WHEN** any code path attempts to update or delete an existing audit record
- **THEN** the operation is rejected (no UPDATE/DELETE grant, enforced in schema)

### Requirement: Global hash chain

Each audit record SHALL carry `prev_hash` and `hash`, where
`hash = sha256(prev_hash ‖ canonical_json(record without hash))` and `prev_hash`
is the `hash` of the immediately preceding record in a single global chain. Each
record SHALL include `seq`, `document_id`, `from_state`, `to_state`, `ts`,
`step`, and `payload`.

#### Scenario: Record links to predecessor

- **WHEN** a new audit record is appended
- **THEN** its `prev_hash` equals the previous record's `hash` and its `hash` is
  computed over its canonical content

#### Scenario: Tamper is detectable

- **WHEN** any stored record's content is altered
- **THEN** recomputing the chain from that point yields a hash mismatch against
  every following record

### Requirement: Derived JSONL export

A hash-chained JSONL export SHALL be producible as a derived, append-only view
of the audit table, carrying the same records and the same hashes, for the
future WORM/object-lock export path. It SHALL NOT be a second source of truth.

#### Scenario: Export mirrors the table

- **WHEN** the JSONL export is generated
- **THEN** each line's record and hash match the corresponding PostgreSQL row

