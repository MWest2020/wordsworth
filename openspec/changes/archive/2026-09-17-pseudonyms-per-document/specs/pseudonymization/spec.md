## ADDED Requirements

### Requirement: Pseudonyms are registered per document

Every anonymisation run SHALL record which pseudonyms it produced for that
document, and a reveal SHALL resolve only pseudonyms registered for the document
it is revealing.

The mapping store is global on purpose — one value, one token, across documents,
which is what makes pseudonymised text searchable. The cost of that choice is
that a token found in any text resolves against the whole store. Neutralising
tokens that arrive in supplied text closes the path an attacker can walk today,
but it is one line of defence at one entrance; a registry closes the exit
instead, and an exit is easier to guard than every entrance.

A token that is not registered for the document being revealed SHALL be left in
place, in the same silent manner as a token whose type is not granted or whose
key does not resolve. A reveal SHALL NOT report which tokens were refused: that
answer is itself an oracle.

Registry rows SHALL carry their provenance. A row written by an anonymisation run
is *minted*; a row written by a backfill that read already-stored text is
*backfilled*, because a backfill cannot tell whether a token was minted there or
arrived before the guard existed. Whoever investigates an incident later should be
able to see that difference rather than assume it.

#### Scenario: A token from another document does not resolve

- **WHEN** a reveal runs on a document whose stored text contains a pseudonym that
  was minted for a different document
- **THEN** that pseudonym is left in place and no clear value is returned for it

#### Scenario: A document's own tokens resolve normally

- **WHEN** a reveal runs with a valid grant on a document's own pseudonyms
- **THEN** those pseudonyms resolve exactly as before

#### Scenario: Registration follows every anonymisation

- **WHEN** a document is anonymised or re-anonymised
- **THEN** the pseudonyms in the resulting text are registered for that document
  with provenance *minted*

#### Scenario: A backfilled row says so

- **WHEN** the registry is backfilled from already-stored text
- **THEN** those rows carry provenance *backfilled*, distinguishable from minted rows
