# observability Specification

## Purpose

Seeing what the pipeline is doing while it does it: metrics, structured logs,
throughput.

This exists because the work is long-running and batched. A run over tens of
thousands of documents that reports only at the end is a run you cannot tell apart
from a hung one, and the usual response to that uncertainty is to kill and restart
it — which is exactly what you do not want with a pipeline that writes.

Logs are structured so they can be queried rather than read, and throughput is
reported so "is this going to finish" has a number behind it.
## Requirements
### Requirement: Metrics endpoint

The API SHALL expose `GET /metrics` in Prometheus text format, including document
counts per state, transition counts per step, and error (failed) counts, derived
from the audit table.

#### Scenario: Metrics reflect the audit state

- **WHEN** `GET /metrics` is called after documents have been processed
- **THEN** it returns Prometheus-format metrics whose per-state counts match the
  current document states

### Requirement: Structured logging

Pipeline transitions SHALL emit structured (JSON) log lines carrying at least the
document id and step.

#### Scenario: A transition logs a structured line

- **WHEN** a document transitions between states
- **THEN** a JSON log line with the document id and step is emitted

### Requirement: Throughput reporting

The run report SHALL include throughput (documents per hour) and per-stage timing,
so batch performance is recorded.

#### Scenario: Run report includes timing

- **WHEN** a batch run completes and its report is produced
- **THEN** the report includes documents-per-hour and per-stage timing

