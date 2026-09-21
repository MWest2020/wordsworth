## ADDED Requirements

### Requirement: Een allow-regel draagt een reden

Every entry in the allow list SHALL carry a human-readable reason, stored beside
the pattern in the same file.

An allow list is the one place in this system where a change quietly results in
*less* pseudonymisation. A bare list of words is a list nobody can review: a
reader cannot tell `^gemeente$` (an ordinary noun) from an entry that silently
exempts a surname. The reason is what makes review possible.

#### Scenario: An entry without a reason is refused

- **WHEN** the lists are loaded and an allow entry has no reason
- **THEN** loading fails, and no list is applied

### Requirement: Een allow-regel mag geen bekende PII onderdrukken

The allow list SHALL be checked against the evaluation corpus, where the seeded
PII values are known, and an entry that suppresses a seeded value SHALL fail the
check.

This is the guard that makes an allow list safe to have at all. Without a corpus
whose answers are known, every entry is a matter of trust; with one, "this rule
hides real PII" is a fact that can be established before the rule ships.

#### Scenario: A rule that hides a seeded value is caught

- **WHEN** an allow entry matches a value the evaluation corpus seeded as PII
- **THEN** the check fails and names the entry

#### Scenario: Recall does not drop

- **WHEN** the evaluation is run with and without the lists
- **THEN** the recall on seeded PII is unchanged

### Requirement: Onderdrukken is zichtbaar in het spoor

Every detection suppressed by the allow list SHALL be counted per type in the
de-identification audit record, and the content hash of the lists SHALL be
recorded with it.

Pseudonymising less is a decision. A decision that leaves no trace is
indistinguishable from a detector that quietly got worse, and the two need very
different responses.

#### Scenario: The record says how much was suppressed and under which lists

- **WHEN** a document is de-identified while lists are active
- **THEN** its audit record carries the per-type suppression counts and the
  lists' content hash

### Requirement: De lijst leeft in de repo, niet in de omgeving

The lists SHALL be versioned in the repository and shipped with the application
image, and SHALL NOT be supplied by an environment that can be changed without
review.

The lists' content hash is recorded in every de-identification record so that a
document can be traced to the rules that produced it. A hash that points at
something anyone could have edited in place is a number without provenance.

#### Scenario: A document can be traced to reviewed rules

- **WHEN** an auditor takes the lists hash from a document's record
- **THEN** it identifies a reviewed commit
