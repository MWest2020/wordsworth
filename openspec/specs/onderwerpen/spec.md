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

### Requirement: A topic name is built from nouns

A computed topic name SHALL consist only of terms that occur as a noun in
their sentence in the group's documents, not as part of a fixed expression.
Pronouns, verbs, adjectives and adverbs SHALL NOT appear in a computed topic
name.

#### Scenario: A pronoun and a verb are left out

- **WHEN** a group's shared text includes "Iedereen steunt de duurzaamheid van het plan"
- **THEN** "duurzaamheid" can name the topic and "iedereen" and "steunt" cannot

#### Scenario: A fixed expression is left out

- **WHEN** "harte" occurs only in "van harte"
- **THEN** "harte" does not appear in a topic name

### Requirement: Computed topic names are unique within a dossier

Two topics in one dossier SHALL NOT show the same computed name.

#### Scenario: Two groups share their top terms

- **WHEN** two topics would both be named "zaal · vergadertijd · rondvraag"
- **THEN** the second takes its next distinguishing noun and the names differ

### Requirement: Topics carry a readable label written by the in-cluster model

Labelling SHALL give a topic a label of at most six words and a one-line
description, written by the configured in-cluster language model from the
summaries of the topic's most central documents and its terms. The label SHALL
be stored and shown as a model's claim, with model and date, alongside the
TF-IDF terms. A label or description that contains a pseudonym token, a
bracketed placeholder or a URL, or a label of more than six words, SHALL be
rejected, and the topic SHALL keep the name it had. A name given by a person SHALL take precedence over a label.

#### Scenario: A topic gets a label

- **WHEN** a topic is labelled and the model answers with a valid label
- **THEN** the topic shows that label, a description, the model and the date, and the TF-IDF terms as subtitle

#### Scenario: An invalid answer is rejected

- **WHEN** the model answers with a label that contains a pseudonym token or a URL
- **THEN** the topic keeps the name it had and the answer says the label was rejected

#### Scenario: A person's name wins

- **WHEN** a topic has both a name given by a person and a label
- **THEN** the name given by the person is shown

### Requirement: Labelling a dossier is a command and the API labels one topic

Labelling every topic of a dossier SHALL be a command
(`python -m wordsworth.onderwerpen_labelen --dossier <name>`) that reports in
one line how many topics it saw, labelled, rejected, skipped, found without
summaries and failed, and ends with a non-zero exit code when a model call failed or the search index
was unreachable. The API SHALL label one topic per call and SHALL NOT offer a
call that labels a whole dossier. A topic computation SHALL NOT call the model.

Labelling SHALL never be silent about what it did not do: when the model is
unreachable no topic loses its name and the result says how many were
labelled, and when the search index is unreachable nothing is labelled and the
result says so.

#### Scenario: The command labels a dossier

- **WHEN** the command runs for a dossier with three topics without a label and the model answers validly
- **THEN** the three topics have a label and the result line says three were labelled

#### Scenario: A second run does not repeat the work

- **WHEN** the command runs again for a dossier whose topics all have a label
- **THEN** the model is not called, the result line says all were skipped, and the exit code is 0

#### Scenario: One topic is labelled through the API

- **WHEN** a caller who may read the corpus asks to label one topic
- **THEN** that topic is labelled and no other topic changes

#### Scenario: A caller who may not read the corpus

- **WHEN** a caller who may not read the corpus asks to label a topic
- **THEN** the call is refused and the model is not called

#### Scenario: The console button does not wait for the model

- **WHEN** a reader presses the label button of a topic in the console
- **THEN** the page returns at once saying the label is being written, and the label is stored when the model has answered

#### Scenario: A topic without summaries

- **WHEN** none of a topic's central documents has a summary
- **THEN** the model is not called, the topic keeps its name and the result says it had no summaries

#### Scenario: The model is down

- **WHEN** labelling runs while the model is unreachable
- **THEN** no topic loses its name and the result says how many were labelled

#### Scenario: The search index is down

- **WHEN** labelling runs while the search index is unreachable
- **THEN** no topic is labelled, no name changes and the result says the index was unreachable
