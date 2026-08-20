## ADDED Requirements

### Requirement: Reversible entity pseudonymisation

Entity PII detected by the entity engine (e.g. PERSON, LOCATION) SHALL be replaced
with stable, per-type keyed pseudonyms and a separated encrypted mapping, exactly
as deterministic PII is, so that entity values are reversible via the mapping store
and revealable selectively by their type's key. A single driver SHALL apply both
the deterministic detectors and the entity engine, and the search-index text SHALL
contain only pseudonyms, never clear entity values.

#### Scenario: A detected name becomes a reversible keyed token

- **WHEN** text containing a personal name is pseudonymised by the reversible
  driver
- **THEN** the name is replaced by a `[PERSON:…]` keyed token, the clear name is
  absent from the output, and deanonymisation with PERSON allowed recovers it

#### Scenario: Entity and deterministic PII compose

- **WHEN** text contains both a name and a BSN
- **THEN** both are replaced by their respective keyed tokens under their own
  type keys, and each is independently revealable by its type

### Requirement: Entity detection failure is fail-hard

If the entity detection engine fails, the reversible driver SHALL raise and SHALL
NOT emit text containing un-pseudonymised entities (no silent fallback). The raised
error SHALL carry no document text.

#### Scenario: Detection error raises without leaking

- **WHEN** the detection engine raises during pseudonymisation
- **THEN** the driver raises an engine error and no text with clear entities is
  returned
