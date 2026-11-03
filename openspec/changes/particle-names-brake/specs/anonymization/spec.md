## ADDED Requirements

### Requirement: The gazetteer is braked by the evaluation corpus

Every entry of the first-name gazetteer SHALL be tested against the evaluation
corpus and against a fixed set of Dutch sentences, in the manner of the
allow-list brake (`tests/test_allow_list_veiligheid.py`): an entry that turns
ordinary text into a `PERSON` is a fact established before roll-out, not a
matter of trust. The brake proves that the rule is exercised and that no
`Ton`-shaped entry is shipped; it does not prove the gazetteer is complete.

#### Scenario: Every gazetteer entry is tested against the corpus

- **WHEN** the brake test runs
- **THEN** each entry of the shipped gazetteer has been tested against the
  evaluation corpus, and an entry that produces a `PERSON` from ordinary text
  fails the test

#### Scenario: An entry the corpus never emits is not counted as passed

- **WHEN** the brake test runs and a shipped entry does not occur in the
  generated corpus as a first name before a particle and last name
- **THEN** the test fails and names that entry as not exercised, rather than
  passing it for lack of a false `PERSON`

#### Scenario: Every entry is run over sentences in the shape the rule matches

- **WHEN** the brake test runs every gazetteer entry over a fixed set of Dutch
  sentences in which the entry stands before a particle and a capitalised
  surname, each sentence stating its expectation
- **THEN** every entry gives the stated expectation on every sentence, at least
  one sentence per particle expects a `PERSON` for the full name and gets it,
  and a sentence without a stated expectation fails the test; this proves the
  rule is exercised and that no `Ton`-shaped entry is shipped, not that the
  gazetteer is complete
