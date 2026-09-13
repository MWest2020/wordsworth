# audit-trail Specification

## Purpose

The record of what happened to every document, chained so that it cannot be
quietly edited.

An append-only store plus a **global hash chain**: the chain is what makes the log
evidence rather than a file the system wrote about itself. The derived JSONL
export exists so that evidence can be read without the database.

Two requirements go beyond bookkeeping. The de-identify step records
**detection aggregates**, so you can see how much was found without the audit
containing what was found. And **a threshold never weakens redaction** — tuning
sensitivity may cause more to be hidden, never less, so no configuration change
can retroactively expose what an earlier run protected.
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

### Requirement: De-identify step records detection aggregates

The audit record for the de-identify step SHALL contain, per detection layer and
entity type, the count of detections and the minimum and maximum score, plus
the count of detections below the configured minimum score. It SHALL contain no
detected value and no text offset.

#### Scenario: Aggregates are present, values are not

- **WHEN** a document with three PERSON entities (scores 0.7, 0.9, 0.95) is
  de-identified
- **THEN** the audit record shows `openanonymiser.PERSON.count == 3`,
  `min_score == 0.7`, `max_score == 0.95`, and no entity text appears anywhere
  in the record

### Requirement: Threshold never weakens redaction

A configured minimum score SHALL only affect counting. Entities below it SHALL
still be redacted before indexing.

#### Scenario: Low-score entity is still redacted

- **WHEN** the minimum score is 0.8 and an entity scores 0.5
- **THEN** the entity is replaced by its token and counted under
  `below_threshold`

