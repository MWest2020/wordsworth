## ADDED Requirements

### Requirement: Changing what a scope returns leaves a trace

Adding or removing a membership SHALL be recorded in the append-only trail
against the document it concerns, naming the caller and the dossier.

A dossier decides what a scoped search answers, so moving a document changes what
someone can and cannot see. Without a record, the result is visible afterwards
and the act is not — and "who moved this, and when" is exactly the question asked
when something turns out to be missing.

Removing a membership SHALL carry a reason; adding one SHALL NOT require it.
Putting something somewhere can be reconstructed from the result; taking it away
cannot.

#### Scenario: A move is visible afterwards

- **WHEN** a document is removed from one dossier and added to another
- **THEN** the trail holds both events against that document, with the caller

#### Scenario: A removal without a reason is refused

- **WHEN** a membership is removed without a reason
- **THEN** it is refused and the membership stays

#### Scenario: Reading leaves nothing

- **WHEN** a dossier is searched
- **THEN** no record is written, because that is a different question with its
  own costs
