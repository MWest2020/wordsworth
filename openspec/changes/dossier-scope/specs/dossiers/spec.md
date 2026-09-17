## ADDED Requirements

### Requirement: A document belongs to a dossier

The system SHALL let documents be grouped into a named dossier, and a document
SHALL be able to belong to more than one.

Content-addressing decides what a document IS: the same bytes are one document.
Delivering the same PDF in two cases must therefore not create two documents, and
must not make the second dossier overwrite the first. Membership is a fact about
a document and a dossier, not a property of either.

Ingestion SHALL name a dossier. Leaving it out SHALL be an error, not a default.

#### Scenario: The same bytes in two dossiers stay one document

- **WHEN** identical content is ingested into two dossiers
- **THEN** there is one document, and it is a member of both

#### Scenario: Ingesting without a dossier is refused

- **WHEN** an ingest request names no dossier
- **THEN** it is refused, and nothing is stored

### Requirement: A search states its scope

Searching SHALL take a dossier scope. Searching across all dossiers SHALL remain
possible as an EXPLICIT choice and SHALL NOT be what happens when the scope is
left out.

A forgotten scope that silently means "everything" is the mistake this exists to
make impossible. In a system that holds personal data, the widest possible answer
must never be the one you get by not thinking.

Results SHALL come only from the dossiers in scope.

#### Scenario: A scoped search answers from that dossier only

- **WHEN** a search names one dossier
- **THEN** no hit comes from a document that is not a member of it

#### Scenario: A search without a scope is refused

- **WHEN** a search names no scope at all
- **THEN** it is refused, and does not fall back to searching everything

#### Scenario: Searching everything is possible and deliberate

- **WHEN** a search explicitly asks for all dossiers
- **THEN** it answers from all of them

### Requirement: Documents ingested before dossiers existed keep their place

The system SHALL place documents that predate dossiers into a dossier naming
their origin, so that a scoped search can still reach them.

A scope that makes the existing corpus unfindable is not a migration but a loss.
The name SHALL say where they came from rather than pretend they were always a
case, because they were not.

#### Scenario: The existing corpus is reachable after the change

- **WHEN** a scoped search is performed over the dossier holding the migrated
  corpus
- **THEN** documents ingested before dossiers existed are found
