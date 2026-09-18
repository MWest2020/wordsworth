## ADDED Requirements

### Requirement: A document belongs to a dossier

The system SHALL let documents be grouped into a named dossier, and a document
SHALL be able to belong to more than one.

Content-addressing decides what a document IS: the same bytes are one document.
Delivering the same PDF in two cases must therefore not create two documents, and
must not make the second dossier overwrite the first. Membership is a fact about
a document and a dossier, not a property of either.

Ingesting content that already exists SHALL add a membership rather than fail.
Ingestion is therefore idempotent on the document and additive on membership. One
PDF that turns up in two cases is one document belonging to two cases, which is
what it is in the world as well.

Ingestion SHALL name a dossier. Leaving it out SHALL be an error, not a default.

#### Scenario: The same bytes in two dossiers stay one document

- **WHEN** identical content is ingested into two dossiers
- **THEN** there is one document, and it is a member of both

#### Scenario: Ingesting content that already exists adds a membership

- **WHEN** content that is already a document is ingested into a dossier it does
  not yet belong to
- **THEN** it becomes a member of that dossier, and this is not an error

#### Scenario: Ingesting into the same dossier twice changes nothing

- **WHEN** the same content is ingested twice into the same dossier
- **THEN** there is still one document with one membership

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

Where there is no store of dossiers to resolve a name against, there is nothing
to scope to, and a scope SHALL NOT be required — requiring one that cannot be
satisfied would leave search unusable. Such a deployment searches everything, as
it did before. This is a condition of the requirement and not a way around it:
the moment dossiers exist, naming one is compulsory.

#### Scenario: A scoped search answers from that dossier only

- **WHEN** a search names one dossier
- **THEN** no hit comes from a document that is not a member of it

#### Scenario: A search without a scope is refused

- **WHEN** a search names no scope at all, and dossiers can be resolved
- **THEN** it is refused, and does not fall back to searching everything

#### Scenario: A deployment without dossiers keeps searching

- **WHEN** a search is performed where no dossiers can be resolved at all
- **THEN** it answers over everything, as it did before

#### Scenario: Searching everything is possible and deliberate

- **WHEN** a search explicitly asks for all dossiers
- **THEN** it answers from all of them

### Requirement: Documents ingested before dossiers existed keep their place

The system SHALL place documents that predate dossiers into a dossier naming
their origin, so that a scoped search can still reach them.

A scope that makes the existing corpus unfindable is not a migration but a loss.
The name SHALL say where they came from rather than pretend they were always a
case, because they were not.

The index holds the dossiers per document, so placing a document into a dossier
SHALL also tell the index. A membership the index does not know about is a
document a scoped search still cannot reach, and the migration would then not
have done the one thing it exists for.

#### Scenario: The existing corpus is reachable after the change

- **WHEN** a scoped search is performed over the dossier holding the migrated
  corpus
- **THEN** documents ingested before dossiers existed are found

#### Scenario: A delivery of known content reaches the index too

- **WHEN** content that is already indexed is delivered into another dossier
- **THEN** the index learns the new membership, so a search scoped to that
  dossier finds it
