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

The exporter re-verifies the exported JSONL and confirms each record and hash
matches the PostgreSQL source before considering an export valid. An export that
does not verify is a failure, not a silent partial.

The existing `verify_chain(session)` verifies the *whole DB chain from genesis*
and takes no JSONL input — it is not the verifier this needs. An incremental
fragment does not start at genesis, so its verification must be **seeded from the
prior export's tail hash**: the fragment's first `prev_hash` must equal that seed,
then each line recomputes and matches its DB row by `seq`. So the builder extends
verification (new fragment-verifier seeded from the last tail), not reuses
`verify_chain` as-is.

## Reused pieces need extending, not reuse as-is

- `export_jsonl(session)` currently dumps the *full* chain (no lower bound).
  Incremental export needs a `since_seq` bound to emit only records after the last
  exported `seq`.
- The `ObjectStore` protocol from `add-object-storage` is only `put/get/exists` —
  no retention parameter. Object Lock (compliance mode) requires setting a
  retain-until date at write time, so this change extends the object-storage seam
  (or a dedicated locked-put path) to carry retention; plain `put` cannot express
  it.

## Incremental export

Export is append-oriented (new records since the last exported `seq`), so it runs
periodically without re-writing history. Retention period is configurable per
bewaartermijn.

## Not in scope

Legal-hold workflows, retention-policy UI, multi-bucket geo-replication.
