## ADDED Requirements

### Requirement: A name with a Dutch particle is one person

Detection SHALL treat a first name, a Dutch particle and a last name as ONE
`PERSON` span. The particles are `van`, `van der`, `van den`, `de`, `ter` and
`ten`; a particle of several words is one particle. The rule applies in the
reversible driver (`reversible_mode` on). The irreversible
`OpenAnonymiserAnonymizer`, used when `reversible_mode` is off, is out of scope
of this requirement. The rule is its own deterministic pattern, not a widening of spans another layer found, and its detections carry
the layer name `dutch_particle_name`.

What identifies a person is the whole name. Detecting the first name and the
last name apart leaves the particle readable or yields several tokens for one
person, and a name missed altogether stays in clear in the anonymised text. The
pilot read of the Gooise Meren dossier found exactly that: a full name shaped
`<first name> ter <last name>` left in a meeting agenda.

The rule SHALL NOT turn ordinary text into a name: a particle between words that
are not a name SHALL NOT yield a `PERSON`. In particular it SHALL NOT match the
name of an institution, which has the same shape of capitalised word, particle,
capitalised word: `Raad van State`, `Kamer van Koophandel`, `Ministerie van
Binnenlandse Zaken`, `Vereniging van Eigenaren` and `Hoogheemraadschap van
Rijnland` stay readable, as an organisation's name is not personal data and
redacting it makes a decision unreadable without protecting anyone.

#### Scenario: A name with each particle is one PERSON

- **WHEN** a synthetic name is built with each of `van`, `van der`, `van den`,
  `de`, `ter` and `ten` between a first name and a last name
- **THEN** each is detected as one `PERSON` span covering the whole name

#### Scenario: The irreversible driver is out of scope

- **WHEN** a document is de-identified by the irreversible
  `OpenAnonymiserAnonymizer`
- **THEN** this requirement does not apply and the rule does not run

#### Scenario: The detection carries its own layer name

- **WHEN** such a name is detected
- **THEN** the detection's layer is `dutch_particle_name`

#### Scenario: No part of the name stays readable

- **WHEN** a document containing such a name is de-identified
- **THEN** the full name (first name, particle and last name together) does not
  appear in the output; an unrelated `van` or `de` elsewhere in the text is
  replaced by value and may remain

#### Scenario: A lowercase particle in ordinary text is not a name

- **WHEN** a sentence contains `de` or `van` between ordinary lowercase words
- **THEN** no `PERSON` is detected

#### Scenario: Raad van State is not a name

- **WHEN** a sentence contains `Raad van State`
- **THEN** no `PERSON` is detected for it

#### Scenario: Kamer van Koophandel is not a name

- **WHEN** a sentence contains `Kamer van Koophandel`
- **THEN** no `PERSON` is detected for it

#### Scenario: Ministerie van Binnenlandse Zaken is not a name

- **WHEN** a sentence contains `Ministerie van Binnenlandse Zaken`
- **THEN** no `PERSON` is detected for it

#### Scenario: Vereniging van Eigenaren is not a name

- **WHEN** a sentence contains `Vereniging van Eigenaren`
- **THEN** no `PERSON` is detected for it

#### Scenario: Hoogheemraadschap van Rijnland is not a name

- **WHEN** a sentence contains `Hoogheemraadschap van Rijnland`
- **THEN** no `PERSON` is detected for it

### Requirement: The particle rule is anchored on a first-name gazetteer

The rule SHALL match only when the word before the particle is an entry of a
first-name gazetteer. Every entry SHALL carry a reason, as entries in
`allow.json` do, and the loader SHALL refuse an entry without one: a bare list
of names that nobody can review is not accepted. A missing or unreadable
gazetteer SHALL be a hard error, not an empty list.

The gazetteer is what keeps institutions out: a word like `Raad`, `Kamer` or
`Ministerie` is not a first name, so the shape `<Capitalised> van <Capitalised>`
alone never yields a `PERSON`.

#### Scenario: A word that is not a listed first name is not a name

- **WHEN** a capitalised word that is not in the gazetteer stands before a
  particle and a capitalised word
- **THEN** no `PERSON` is detected for it

#### Scenario: A gazetteer entry without a reason is refused

- **WHEN** the gazetteer is loaded with an entry that has no reason, or a blank
  one
- **THEN** loading fails and names the entry

#### Scenario: A missing gazetteer is an error

- **WHEN** the gazetteer file is absent or unreadable
- **THEN** the rule fails loudly and does not run with an empty list

### Requirement: The gazetteer is braked by the evaluation corpus

Every entry of the first-name gazetteer SHALL be tested against the evaluation
corpus, in the manner of the allow-list brake
(`tests/test_allow_list_veiligheid.py`): an entry that turns ordinary text into a
`PERSON` is a fact established before roll-out, not a matter of trust. A first
name that is also a common capitalised word at sentence start (`Ton`, `Wil`,
`Bart`) SHALL NOT be a gazetteer entry. This costs recall on purpose: of the 14
seeded first names in `eval/synthetic.py`, `Ton` and `Bart` stay unmatched, a
known and accepted miss traded for precision. The gazetteer file is not part of
`lists_hash`.

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

#### Scenario: A first name that is a common word is excluded

- **WHEN** the shipped gazetteer is listed
- **THEN** it holds none of `Ton`, `Wil` and `Bart`

#### Scenario: The excluded names stay unmatched

- **WHEN** `Ton` or `Bart` stands before a particle and a last name
- **THEN** no `PERSON` is detected by this rule, a known and accepted miss

#### Scenario: A gazetteer change does not alter lists_hash

- **WHEN** the gazetteer file changes
- **THEN** `lists_hash` is unchanged

### Requirement: The audit aggregate counts a person once

When a shorter detected span lies inside a longer one for the same person, such
as the bare first name returned next to the full-name span, the per-layer audit
aggregate SHALL absorb the shorter span into the longer one and count the person
once. Only the aggregate is affected; what is replaced in the text SHALL NOT
change.

#### Scenario: A bare first name next to the full name is counted once

- **WHEN** an entity layer returns the bare first name and the full name of the
  same person
- **THEN** the aggregate counts that person once, for the longer span

#### Scenario: Replacement is unaffected by the deduplication

- **WHEN** the same text is de-identified with and without the deduplication
- **THEN** the output text is identical

### Requirement: The particle rule is not a deterministic detector

The rule that detects a name with a Dutch particle SHALL NOT be a row in the
shared detector table (`detectors.DETECTORS`). That table holds validated,
high-precision values, and it is read by the anonymizer, the pseudonymizer,
`find_deterministic()`, the PII evaluation's deterministic layer and the dataset
column validation. A name rule is neither validated nor high-precision, and a
row there would change what all of those report without anyone having chosen
it: the evaluation would score a name rule as a deterministic layer, and a
dataset column of organisation names would be classified as holding `PERSON`.

#### Scenario: The detector table is unchanged

- **WHEN** the labels in `detectors.DETECTORS` are listed
- **THEN** they are `bsn`, `iban`, `email` and `postcode`, and no other

#### Scenario: find_deterministic ignores a name with a particle

- **WHEN** `find_deterministic()` is given a text holding a first name, a
  particle and a last name
- **THEN** it returns no hit for that name

#### Scenario: The PII evaluation's deterministic layer is unchanged

- **WHEN** the deterministic layer of the PII evaluation runs on a text holding
  such a name
- **THEN** it predicts no entity for it

#### Scenario: The rule is measurable as its own layer

- **WHEN** the PII evaluation is run with the layer `dutch_particle_name` added
  to its default layers
- **THEN** that layer detects the name as `PERSON`, and the default layers,
  run without it, give the results they gave before
