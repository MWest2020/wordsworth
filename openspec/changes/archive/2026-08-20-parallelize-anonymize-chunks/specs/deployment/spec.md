## ADDED Requirements

### Requirement: Concurrent, order-preserving chunk anonymization

The anonymization driver SHALL dispatch a document's chunks to the OpenAnonymiser
service concurrently, bounded by the configured concurrency, and SHALL reassemble
the redacted chunks in their original order so the concatenated result is
independent of completion timing. Total in-flight calls SHALL NOT exceed the
process-wide concurrency cap. If any chunk fails, the driver SHALL raise (the
caller turns this into a hard `AnonymizationEngineError`) and SHALL NOT emit
partial or un-redacted text.

#### Scenario: Chunks complete out of order

- **WHEN** a document's chunks are anonymized concurrently and complete in a
  different order than submitted
- **THEN** the reassembled text is the in-order concatenation of the redacted
  chunks, identical to serial redaction

#### Scenario: One chunk fails

- **WHEN** any single chunk's anonymize call fails
- **THEN** the whole document's anonymization fails hard and no partial text is
  returned

### Requirement: OpenAnonymiser uses aggregate cluster CPU

The OpenAnonymiser service SHALL run one replica per worker node (anti-affinity
on hostname) so that a document's concurrent chunk calls are load-balanced across
nodes, using the cluster's aggregate CPU rather than a single core. Per-replica
resource limits SHALL be sized for the chunk-bounded working set, not the
whole-document one.

#### Scenario: Replicas are spread across nodes

- **WHEN** the service is deployed
- **THEN** replicas are scheduled one per worker node and the Service balances
  concurrent anonymize calls across them
