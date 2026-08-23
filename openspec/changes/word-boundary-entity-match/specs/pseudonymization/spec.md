## ADDED Requirements

### Requirement: Entity matching is whole-word

Reversible entity redaction and the survivor fail-hard check SHALL match a
detected value only when it occurs as a whole token (not embedded in a larger
word). A fragment appearing only inside larger words SHALL be neither redacted
nor treated as a survivor; a genuine whole-word occurrence SHALL still be redacted
and, if it survives, still fail hard.

#### Scenario: A fragment inside a word is ignored

- **WHEN** a detected value appears only as a substring within larger words
- **THEN** those words are left intact and no fail-hard is raised

#### Scenario: A whole-word entity is still redacted

- **WHEN** a detected value appears as a whole word
- **THEN** it is replaced by its keyed token
