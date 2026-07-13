# Tasks — add-audit-worm-export

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
DEPENDS ON: add-object-storage (S3 Object Lock bucket) — build that first.

## 1. WORM export
- [ ] 1.1 Extend the `ObjectStore` seam (or add a locked-put path) to carry an
      Object-Lock retain-until date; plain `put/get/exists` cannot express it
- [ ] 1.2 Export derived JSONL to an S3 Object Lock (compliance-mode) bucket with
      a configurable retention period (depends on object-storage)
- [ ] 1.3 Incremental: add a `since_seq` bound to `export_jsonl` (today it dumps
      the full chain) and export only records after the last exported `seq`
- [ ] 1.4 Tests (skip if no Object-Lock backend): exported object is retention-locked

## 2. Verification
- [ ] 2.1 Fragment verifier seeded from the prior export's tail hash: first
      `prev_hash` equals the seed, each line recomputes and matches its DB row by
      `seq`; non-verifying = failure. (Not `verify_chain`, which walks the whole
      DB from genesis and takes no JSONL input.)
- [ ] 2.2 Tests: matching fragment verifies; altered record, seq gap, or wrong
      first `prev_hash` is rejected

## 3. Retention
- [x] 3.1 Retention period configurable per bewaartermijn
