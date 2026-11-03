## ADDED Requirements

### Requirement: The audit aggregate counts a person once

When a shorter detected `PERSON` value lies inside a longer `PERSON` value
of the same document, such as the bare first name returned next to the full-name
span, the per-layer audit aggregate SHALL absorb the shorter value into the
longer one and count the person once. Containment SHALL be decided by value
(whole words of the shorter value occurring as whole words in the longer one),
not by offsets. Only the aggregate is affected; what is replaced in the text SHALL NOT
change.

#### Scenario: A bare first name next to the full name is counted once

- **WHEN** an entity layer returns the bare first name and the full name of the
  same person
- **THEN** the aggregate counts that person once, for the longer span

#### Scenario: Replacement is unaffected by the deduplication

- **WHEN** the same text is de-identified with and without the deduplication
- **THEN** the output text is identical

#### Scenario: Two people sharing a first name are both counted

- **WHEN** a document names two different people with the same first name and
  different last names, and an entity layer also returns the bare first name
- **THEN** the aggregate counts two people, not one and not three
