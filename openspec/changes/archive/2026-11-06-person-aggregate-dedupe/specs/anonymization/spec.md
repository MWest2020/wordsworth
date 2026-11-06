## ADDED Requirements

### Requirement: The audit aggregate counts a person once

When a shorter detected `PERSON` value lies inside a longer `PERSON` value
of the same document, such as the bare first name returned next to the full-name
span, the per-layer audit aggregate SHALL drop every detection of the shorter value
and keep the rows of the longer one, so the person counts once per detection of
the longer value. Equal values SHALL keep one row per occurrence, as before. Containment SHALL be decided by value
(whole words of the shorter value occurring as whole words in the longer one),
not by offsets. Only the aggregate is affected; what is replaced in the text SHALL NOT
change.

#### Scenario: A bare first name next to the full name adds no row

- **WHEN** an entity layer returns the bare first name and the full name of the
  same person
- **THEN** the aggregate holds only the full-name rows, and the bare first name
  adds none

#### Scenario: Replacement is unaffected by the deduplication

- **WHEN** the same text is de-identified with and without the deduplication
- **THEN** the output text is identical

#### Scenario: Two people sharing a first name are both counted

- **WHEN** a document names two different people with the same first name and
  different last names, and an entity layer also returns the bare first name
- **THEN** the aggregate holds two rows, one per full name, and the bare first
  name adds none

#### Scenario: Equal values keep one row per occurrence

- **WHEN** an entity layer returns the same `PERSON` value twice
- **THEN** the aggregate holds two rows for it, as before this change
