## ADDED Requirements

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
