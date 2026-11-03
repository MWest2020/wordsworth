## ADDED Requirements

### Requirement: The particle rule is measurable as its own evaluation layer

The PII evaluation (`eval/pii_run.py`) and the overdetection run
(`eval/overdetection_run.py`) SHALL offer `dutch_particle_name` as an explicit,
opt-in layer; their default layers SHALL stay `deterministic,openanonymiser`.
Results SHALL be reported as measured: the second PERSON number is full-pipeline
recall, recall on real documents is stated as unknown, and a run that cannot
reach the service records "not run", never an estimate.

#### Scenario: The rule is measurable as its own layer

- **WHEN** the PII evaluation is run with the layer `dutch_particle_name` added
  to its default layers
- **THEN** that layer detects the name as `PERSON`, and the default layers,
  run without it, give the results they gave before

#### Scenario: Recall on real documents is not claimed

- **WHEN** the measurements are recorded
- **THEN** the evaluation docs state that recall on real documents is unknown
  and that the Gooise Meren miss is not closed by this change
