# observability Specification

## Purpose
TBD - created by archiving change add-observability. Update Purpose after archive.
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

