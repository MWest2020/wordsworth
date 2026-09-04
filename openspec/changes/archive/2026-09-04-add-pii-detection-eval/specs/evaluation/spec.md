## ADDED Requirements

### Requirement: PII detection metrics

The evaluation library SHALL compute, for a gold corpus of annotated spans,
precision, recall and F1 per entity type and overall, at span level (exact
match) and token level (overlap), and SHALL report the number of gold entities
with no overlapping detection (`leaks`). When detections carry a layer, the
metrics SHALL also be reported per layer.

#### Scenario: Exact and partial matches are distinguished

- **WHEN** gold has `Janine van Dijk` and the detector finds `van Dijk`
- **THEN** span-level recall for PERSON is 0, token-level recall is 2/3, and
  `leaks` is 0

#### Scenario: A missed entity is a leak

- **WHEN** a gold BSN has no overlapping detection
- **THEN** `leaks` increases by one and BSN recall decreases accordingly
