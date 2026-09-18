# dossiers Specification

## Purpose

The scope a search has to state.

Searching everything by default means that forgetting the scope and having no
scope are the same thing. In a system that holds personal data the widest answer
must never be the one you get by not thinking — so a dossier is named, and
"everything" is spelled out.

A dossier is what a case is in the world: a Woo request, a delivery, a matter.
Membership is a fact about a PAIR, because content-addressing already decides
what a document IS — the same bytes are one document, so the same PDF delivered
in two cases belongs to both and becomes neither a copy nor an overwrite.

## Requirements

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

### Requirement: A membership can be undone, and a dossier renamed

Removing a membership SHALL be possible, and removing one that is not there
SHALL NOT be an error. Renaming a dossier SHALL move no document: the identity is
the dossier, not the word used for it.

Without this, a document placed in the wrong dossier stays there forever, and the
first attempt at classifying a corpus becomes the last. Correcting a mistake must
cost less than making it.

#### Scenario: A document can be moved between dossiers

- **WHEN** a membership is removed and another added
- **THEN** a search scoped to the old dossier no longer finds the document, and
  one scoped to the new dossier does

#### Scenario: Renaming keeps every membership

- **WHEN** a dossier is renamed
- **THEN** the same documents belong to it, and a search under the new name
  answers exactly as the old name did

### Requirement: A document that belongs nowhere is reported

Removing the last membership of a document SHALL be allowed and SHALL be counted
and reported, never passed over silently.

Such a document is invisible to every scoped search. That may be exactly what was
intended in the middle of a re-classification, so it is not refused — but it is
the state in which a document is most easily lost, and the moment it happens is
the moment someone can still act on it.

#### Scenario: Losing the last membership is reported

- **WHEN** an operation leaves documents in no dossier at all
- **THEN** it reports how many, rather than completing quietly

### Requirement: Documents are assigned from recorded provenance, never guessed

Assigning documents to dossiers in bulk SHALL use provenance recorded per
document. A document with no provenance entry SHALL NOT be assigned, and SHALL be
counted and reported.

A classification derived from a date or a text pattern is one nobody can retell
afterwards, and that is worse than none. Provenance says where a document came
from because something wrote it down at the time; anything else is inference
wearing the same clothes.

#### Scenario: A document without provenance is left alone

- **WHEN** a bulk assignment runs and a document has no provenance entry
- **THEN** it is not assigned to anything, and the count is reported

#### Scenario: Provenance naming the same origin groups documents together

- **WHEN** several documents record the same origin
- **THEN** they end up in one dossier named after it
