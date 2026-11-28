## ADDED Requirements

### Requirement: The switch to the key service leaves reveal alone

The cutover's switch of pseudonymise, originals, open-limits and delete SHALL
NOT change the reveal routes, their driver, their statuses or their
authorisation. A reveal that needs a signed identity from the caller is a
separate change, after the question of callers without a signed assertion is
answered.

#### Scenario: Reveal behaves as before the switch

- **WHEN** the other operations use the key service's drivers
- **THEN** the reveal routes use their in-process driver and answer exactly as
  before

#### Scenario: A caller without a signed assertion still reveals

- **WHEN** the other operations use the key service's drivers and a caller who
  is covered by a grant but carries no signed assertion reveals
- **THEN** the endpoint decides as it did before the switch
