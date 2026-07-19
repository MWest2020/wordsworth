## Why

Fase 6 (productieklaar). To run and trust the pipeline we need visibility:
health, metrics (throughput, per-state counts, stage durations, errors), and
structured logs. Sovereign — no external APM/telemetry.

## What Changes

- Add a **`GET /metrics`** endpoint in Prometheus text format: documents per
  state, documents processed, per-stage durations, error counts.
- Add **structured (JSON) logging** across pipeline stages with the document id
  and step.
- Formalise a **pipeline throughput/latency report** (extends the existing run
  report) so batch runs record docs/hour and per-stage timing.

## Capabilities

### New Capabilities
- `observability`: metrics endpoint, structured logs, and throughput reporting.

## Impact

- Metrics derived largely from the audit table (counts per `to_state`, timings
  from record timestamps). Local only; no cloud telemetry. `/health` already
  exists. Does not touch `CLAUDE.md`, `.claude/agents/`, CI.
