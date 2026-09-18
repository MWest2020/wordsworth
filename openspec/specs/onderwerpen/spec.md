# onderwerpen Specification

## Purpose

Laten zien waar een dossier over gaat, voordat iemand zijn eerste zoekterm
verzint. Een onderwerp is een groep documenten binnen één dossier, met een naam
uit de termen die die groep onderscheiden van de rest.

Een onderwerp **versmalt het zoeken en raakt de rangschikking niet.** Dat twee
documenten op elkaar lijken zegt dat ze op elkaar lijken; het zegt niet dat ze
allebei antwoord geven op de vraag die iemand stelt. Cluster-lidmaatschap in de
score verwerken zou de volgorde verschuiven om een reden die niemand aan de
lezer kan uitleggen.

Daarom staat hier ook wat een onderwerp níet mag zijn: het hele dossier (dan is
het geen indeling), een naam met een pseudonym-token erin (die belandt op
schermen, in exports en in URL's, waar de reveal-gate nooit kijkt), of een lijst
zonder het moment en het aantal waarover gerekend is (die leest als de huidige
stand van het dossier, ook als hij maanden oud is).

## Requirements

### Requirement: Onderwerpen zijn groepen documenten binnen één dossier

The system SHALL compute, per dossier and on request, a set of topics; each
topic is a group of documents from that dossier and carries a name derived from
the terms that distinguish the group from the rest of the same dossier.

A topic SHALL NOT span dossiers. The dossier is the search scope, and a topic
that crossed that border would make a scope out of something the caller never
chose.

The stored result SHALL carry the moment it was computed and the number of
documents it was computed over.

#### Scenario: A topic view says how old it is

- **WHEN** a dossier has grown since its topics were computed
- **THEN** the topic view still shows the stored topics, together with the
  moment and the document count they were computed over

#### Scenario: Topics are not computed during ingest

- **WHEN** a document is ingested into a dossier that already has topics
- **THEN** the stored topics are unchanged and no clustering runs

### Requirement: Een onderwerpnaam bevat nooit een token en nooit een klaarwaarde

A topic name SHALL contain no pseudonym token and no clear PII value.

Topics are computed over pseudonymised text, so a distinguishing term can be a
token such as `[PERSOON:3fa9c2d1]`. A topic name reaches screens, exports and
URLs; a token there is a leak of the fact that this document is about this
person, and it travels to places the reveal gate never sees.

A computed name SHALL be recognisable as computed. A person MAY rename a topic;
the given name replaces the computed one and the computed one SHALL remain
retrievable.

#### Scenario: A token never becomes part of a name

- **WHEN** a distinguishing term of a group is a pseudonym token
- **THEN** it is left out of the name, and the name is formed from the remaining
  terms

#### Scenario: A renamed topic keeps its computed name

- **WHEN** a person renames a topic
- **THEN** the view shows the given name and the computed name stays available
  as the origin of that group

### Requirement: Een onderwerp versmalt de zoekscope en raakt de score niet

Searching within a topic SHALL narrow the set of documents considered and SHALL
NOT change the relative order of the documents that remain.

Membership of a cluster says that documents resemble one another. It does not
say that they answer the question asked. Letting it move the score would make
"resembles its neighbours" into a form of relevance, and the resulting order
could not be explained to the person reading it.

#### Scenario: The same hit ranks the same inside a topic

- **WHEN** a query is run over a dossier and again over a topic within it
- **THEN** the documents that appear in both results stand in the same order
  relative to one another

#### Scenario: A topic scope narrows to its own documents

- **WHEN** a query is run within a topic
- **THEN** only documents belonging to that topic can appear in the result

### Requirement: De onderwerpindeling is meetbaar tegen een bekende waarheid

The evaluation corpus SHALL carry a known topic per generated document, and the
evaluation SHALL report both the agreement between the computed grouping and
that known topic, and the existing retrieval metrics with and without a topic
scope over the same queries.

Without a number, "smarter search" is a feeling. Two numbers, because grouping
quality and retrieval quality are different questions and a good answer to one
does not imply the other.

#### Scenario: The generator writes a known topic per document

- **WHEN** the ground-truth corpus is generated
- **THEN** every document's record carries the topic it was generated for

#### Scenario: The evaluation reports both numbers

- **WHEN** the evaluation is run over a corpus with topics
- **THEN** the report contains the grouping agreement and the retrieval metrics
  for both the unscoped and the topic-scoped run
