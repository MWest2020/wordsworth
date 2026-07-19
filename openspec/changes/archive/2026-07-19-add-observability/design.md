# Design decisions — add-observability

## Metrics from the audit table

The append-only audit table already records every transition with a timestamp, so
most metrics are queries over it — no separate metrics store to keep consistent:

- `wordsworth_documents_total{state=...}` — count of documents whose current state
  is each state (the run-report query).
- `wordsworth_transitions_total{step=...}` — transition counts per step.
- stage duration — derived from consecutive transition timestamps per document.
- error counts — transitions to `failed` (with reason category).

Exposed at `GET /metrics` in Prometheus text format (no client dependency needed
to emit it — plain text).

## Structured logs

JSON lines with `document_id`, `step`, `from`, `to`, `duration_ms`, `level`. One
formatter; each pipeline transition logs one line. Greppable and machine-parseable
without an external collector.

## Throughput reporting

Extend the existing run report with docs/hour and per-stage mean/percentile
timing, so a batch run's throughput is recorded (the "measure and report
throughput" scoping rule) — the later customer story of reproducible performance
on standard iron.

## Boundaries

Local only — no external APM/tracing SaaS (sovereign). Prometheus text is a
format, not a hosted service; scraping is the operator's choice.

## Not in scope

Distributed tracing, dashboards, alerting rules.
