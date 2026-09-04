## ADDED Requirements

### Requirement: De-identify step records detection aggregates

The audit record for the de-identify step SHALL contain, per detection layer and
entity type, the count of detections and the minimum and maximum score, plus
the count of detections below the configured minimum score. It SHALL contain no
detected value and no text offset.

#### Scenario: Aggregates are present, values are not

- **WHEN** a document with three PERSON entities (scores 0.7, 0.9, 0.95) is
  de-identified
- **THEN** the audit record shows `openanonymiser.PERSON.count == 3`,
  `min_score == 0.7`, `max_score == 0.95`, and no entity text appears anywhere
  in the record

### Requirement: Threshold never weakens redaction

A configured minimum score SHALL only affect counting. Entities below it SHALL
still be redacted before indexing.

#### Scenario: Low-score entity is still redacted

- **WHEN** the minimum score is 0.8 and an entity scores 0.5
- **THEN** the entity is replaced by its token and counted under
  `below_threshold`
