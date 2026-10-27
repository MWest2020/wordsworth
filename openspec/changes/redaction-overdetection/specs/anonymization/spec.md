## ADDED Requirements

### Requirement: An over-detection change is measured before and after

A change that reduces what detection redacts (an allow entry or a score
threshold) SHALL be measured on the evaluation corpus both before and after the
change, on the same corpus and the same detections, and both results SHALL be
recorded with their date. Recall on seeded PII and the number of leaks SHALL be
unchanged by the change.

The effect of the change across a reprocess SHALL be read from the run's own
`suppressed_by_list` counts, not from comparing the index before and after.

#### Scenario: The before and after are recorded

- **WHEN** an allow entry or threshold that reduces redaction is introduced
- **THEN** the baseline and the result are recorded with their date, per type

#### Scenario: Recall does not move

- **WHEN** the evaluation is run after the change
- **THEN** recall on seeded PII and the leak count equal the baseline

### Requirement: A reduction in redaction needs a human decision per value

An entry that stops a value being redacted SHALL be added only after a human has
decided that the value is not PII, and SHALL carry that reason. The system and
its build agents SHALL NOT read document text to find candidate values.

#### Scenario: An allow entry without a reason is refused

- **WHEN** the lists are loaded and an allow entry has no reason
- **THEN** loading fails, and no list is applied
