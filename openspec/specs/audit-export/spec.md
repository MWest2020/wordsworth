# audit-export Specification

## Purpose
TBD - created by archiving change add-audit-worm-export. Update Purpose after archive.
## Requirements
### Requirement: WORM export of the audit chain

The hash-chained audit stream SHALL be exportable to S3 Object Lock storage in a
write-once mode with a retention period, so exported records cannot be altered or
deleted before expiry.

#### Scenario: Exported records are locked

- **WHEN** the audit chain is exported to the Object Lock bucket
- **THEN** the exported objects carry a retention lock and cannot be overwritten
  or deleted before the retention period expires

### Requirement: Export verifies against the database

An export SHALL be considered valid only if its chain re-verifies (each record's
hash links correctly and matches the PostgreSQL source). A non-verifying export
SHALL be a failure, not a silent partial.

#### Scenario: Tampered or partial export is rejected

- **WHEN** the exported chain does not re-verify against the database
- **THEN** the export is reported as failed

### Requirement: Incremental export with retention

Export SHALL be incremental (records after the last exported `seq`) and SHALL
apply a configurable retention period per bewaartermijn.

#### Scenario: Only new records are exported

- **WHEN** an export runs after a prior export
- **THEN** only records newer than the last exported `seq` are written

