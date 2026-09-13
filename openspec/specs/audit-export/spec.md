# audit-export Specification

## Purpose

Getting the audit chain out to WORM storage, where it is no longer ours to change.

An audit chain that lives only in the database it audits proves less than it
looks like it proves. Exporting it to write-once storage moves the evidence
outside the reach of the system that produced it.

**The export verifies against the database**, so a divergence is detected at the
moment it is exportable rather than at the moment someone asks. Incremental with
retention, because an audit that is too expensive to export regularly ends up
exported once.
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

