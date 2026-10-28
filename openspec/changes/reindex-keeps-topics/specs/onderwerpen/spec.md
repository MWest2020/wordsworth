## MODIFIED Requirements

### Requirement: Onderwerpen zijn groepen documenten binnen één dossier

The system SHALL compute, per dossier and on request, a set of topics; each
topic is a group of documents from that dossier and carries a name derived from
the terms that distinguish the group from the rest of the same dossier.

A topic SHALL NOT span dossiers. The dossier is the search scope, and a topic
that crossed that border would make a scope out of something the caller never
chose.

The stored result SHALL carry the moment it was computed and the number of
documents it was computed over.

A document that is re-indexed by `reanonymize` (and so by reprocess) SHALL keep
the topics it had in the index. Searching within a topic SHALL find the same
documents after a reprocess as before it.

#### Scenario: A topic view says how old it is

- **WHEN** a dossier has grown since its topics were computed
- **THEN** the topic view still shows the stored topics, together with the
  moment and the document count they were computed over

#### Scenario: Topics are not computed during ingest

- **WHEN** a document is ingested into a dossier that already has topics
- **THEN** the stored topics are unchanged and no clustering runs

#### Scenario: A reprocessed document is still found within its topic

- **WHEN** an indexed document belongs to a topic and is reprocessed
- **THEN** a search within that topic still returns the document
