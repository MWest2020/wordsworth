## ADDED Requirements

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
