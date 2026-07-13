# Tasks — add-observability

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Metrics
- [ ] 1.1 `GET /metrics` (Prometheus text): documents per state, transitions per
      step, failed counts — derived from the audit table
- [ ] 1.2 Tests: per-state counts match processed documents

## 2. Structured logging
- [ ] 2.1 JSON log line on each ACTUAL transition (document_id, step, from, to,
      level); no-op transitions log nothing; no emit-time duration
- [ ] 2.2 Tests: a transition emits a parseable JSON line with id + step; a no-op
      transition emits none

## 3. Throughput report
- [ ] 3.1 Extend run report with docs/hour + per-stage timing (post-hoc from
      consecutive audit timestamps), labelled as wall-clock latency not compute
- [ ] 3.2 Tests: report includes throughput and timing fields
