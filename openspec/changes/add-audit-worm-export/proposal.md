## Why

The audit trail is append-only and hash-chained in PostgreSQL. The 10-year
tamper-evidence requirement (gap 3) needs the chain exported to WORM storage:
write-once, object-locked, retained per the applicable bewaartermijnen, and
verifiable against the database.

## What Changes

- Add a **WORM export**: write the derived hash-chained JSONL audit stream to an
  S3 **Object Lock** (compliance-mode) bucket, so exported records cannot be
  altered or deleted for the retention period.
- Add **export verification**: the exported chain re-verifies (hashes link, match
  the database) so an audit can be proven intact.
- Add **retention** configuration per bewaartermijn.

## Capabilities

### New Capabilities
- `audit-export`: WORM/object-lock export of the audit chain, its verification,
  and retention.

## Impact

- Depends on `object-storage` (S3 Object Lock; Ceph RGW / SeaweedFS support it),
  whose `ObjectStore` seam this change extends to carry Object-Lock retention.
  Extends the derived JSONL export (`since_seq` bound) and adds a fragment
  verifier seeded from the prior export's tail (the existing `verify_chain` walks
  the whole DB from genesis and cannot verify an incremental fragment). Read-only
  over the audit table (never mutates it). Does not touch `CLAUDE.md`,
  `.claude/agents/`, CI.
