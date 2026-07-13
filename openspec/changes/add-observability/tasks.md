# Tasks — add-observability

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Metrics
- [x] 1.1 `GET /metrics` (Prometheus text): documents per state, transitions per
      step, failed counts — derived from the audit table
- [x] 1.2 Tests: per-state counts match processed documents

## 2. Structured logging
- [x] 2.1 JSON log lines on each transition (document_id, step, from, to, duration)
- [x] 2.2 Tests: a transition emits a parseable JSON line with id + step

## 3. Throughput report
- [x] 3.1 Extend run report with docs/hour + per-stage timing
- [x] 3.2 Tests: report includes throughput and timing fields
