# Tasks — add-audit-worm-export

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. WORM export
- [ ] 1.1 Export derived JSONL to an S3 Object Lock (compliance-mode) bucket with
      a configurable retention period (depends on object-storage)
- [ ] 1.2 Incremental: export only records after the last exported `seq`
- [ ] 1.3 Tests (skip if no Object-Lock backend): exported object is retention-locked

## 2. Verification
- [ ] 2.1 Re-verify the exported chain against PostgreSQL; non-verifying = failure
- [ ] 2.2 Tests: matching export verifies; altered/partial export is rejected

## 3. Retention
- [ ] 3.1 Retention period configurable per bewaartermijn
