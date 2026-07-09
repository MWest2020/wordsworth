# Design decisions — add-audit-worm-export

## Export target: S3 Object Lock (compliance mode)

Write the derived hash-chained JSONL (from change a) to a bucket with Object Lock
in **compliance mode** and a retention period. Compliance mode means not even a
root/admin can delete or overwrite before expiry — that is the WORM guarantee the
10-year requirement needs. Ceph RGW and SeaweedFS both support S3 Object Lock.

## Two layers of tamper-evidence

1. **Hash chain** (already): any alteration breaks the chain, detectable by the
   verifier.
2. **WORM at rest** (new): the exported object physically cannot be changed for
   the retention window.

Together: alteration is both prevented (WORM) and detectable (chain).

## Verification

The exporter re-runs the chain verifier over the exported JSONL and confirms each
record and hash matches the PostgreSQL source before considering an export valid.
An export that does not verify is a failure, not a silent partial.

## Incremental export

Export is append-oriented (new records since the last exported `seq`), so it runs
periodically without re-writing history. Retention period is configurable per
bewaartermijn.

## Not in scope

Legal-hold workflows, retention-policy UI, multi-bucket geo-replication.
