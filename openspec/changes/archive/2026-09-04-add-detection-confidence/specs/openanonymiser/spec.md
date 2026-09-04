## ADDED Requirements

### Requirement: Detections carry layer and confidence

Every detected entity SHALL carry the detection layer that produced it
(`deterministic` or `openanonymiser`) and a confidence score in `[0, 1]`.
Deterministic detectors SHALL report `1.0`. The OpenAnonymiser driver SHALL pass
the service's `score` through and SHALL fail hard when an entity arrives without
one.

#### Scenario: Service score is preserved

- **WHEN** OpenAnonymiser returns an entity with `score: 0.85`
- **THEN** the detection handed to the pseudonymiser carries `score == 0.85`
  and `layer == "openanonymiser"`

#### Scenario: Missing score is a hard error

- **WHEN** an entity in `entities_found` lacks `score`
- **THEN** the document fails the de-identify step; nothing is indexed
