## ADDED Requirements

### Requirement: WORM export of the audit chain

The hash-chained audit stream SHALL be exportable to S3 Object Lock storage in a
write-once mode with a retention period, so exported records cannot be altered or
deleted before expiry.

#### Scenario: Exported records are locked

- **WHEN** the audit chain is exported to the Object Lock bucket
- **THEN** the exported objects carry a retention lock and cannot be overwritten
  or deleted before the retention period expires

### Requirement: Export verifies against the database

An export SHALL be considered valid only if its chain re-verifies: each exported
record's hash SHALL recompute correctly and match the PostgreSQL source row for
that `seq`. Because export is incremental, an exported fragment does NOT begin at
genesis — verification of a fragment SHALL be **seeded from the tail hash of the
prior export** (the fragment's first `prev_hash` SHALL equal that seed), so the
links across export boundaries are checked, not just within a fragment. A
non-verifying export SHALL be a failure, not a silent partial.

#### Scenario: Tampered or partial export is rejected

- **WHEN** an exported fragment does not re-verify against the database (a hash
  mismatches, a record diverges from its PostgreSQL row, or the fragment's first
  `prev_hash` does not equal the prior export's tail hash)
- **THEN** the export is reported as failed

#### Scenario: A fragment links to the prior export

- **WHEN** an incremental fragment is verified
- **THEN** its first record's `prev_hash` matches the last exported record's hash
  and every subsequent link recomputes correctly

### Requirement: Incremental export with retention

Export SHALL be incremental (records after the last exported `seq`) and SHALL
apply a configurable retention period per bewaartermijn.

#### Scenario: Only new records are exported

- **WHEN** an export runs after a prior export
- **THEN** only records newer than the last exported `seq` are written
