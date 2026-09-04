## ADDED Requirements

### Requirement: Every PII type has a category and a legal basis

wordsworth SHALL hold a static, versioned registry that maps every PII entity
type to exactly one category — `c1` (AVG Art. 6, ordinary personal data), `c2`
(AVG Art. 9, special categories) or `c3` (AVG Art. 10, criminal data) — and a
minimum Privacy Protection Level (PPL) at which that category may be revealed:
`c1 → 1`, `c2 → 2`, `c3 → 3`. An entity type unknown to the registry SHALL be
treated as `c1` and logged once per process.

#### Scenario: Known type resolves to its category

- **WHEN** the registry is asked for the category of `GEZONDHEID`
- **THEN** it returns `c2`, legal basis `Art. 9`, PPL minimum 2

#### Scenario: Unknown type is fail-safe

- **WHEN** the registry is asked for a type it does not know
- **THEN** it returns `c1` (never revealed at PPL 0) and emits one warning

### Requirement: PPL level expands to a type set

The registry SHALL expand a PPL level `n` in `0..3` to the set of all entity
types whose category has PPL minimum `≤ n`. PPL 0 SHALL expand to the empty set.

#### Scenario: PPL 2 covers Art. 6 and Art. 9

- **WHEN** PPL 2 is expanded
- **THEN** the set contains every `c1` and `c2` type and no `c3` type

#### Scenario: PPL 0 reveals nothing

- **WHEN** PPL 0 is expanded
- **THEN** the set is empty
