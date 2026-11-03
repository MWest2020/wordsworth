## ADDED Requirements

### Requirement: A name with a Dutch particle is one person

In the reversible driver, detection SHALL treat a first name, a Dutch particle
(`van`, `van der`, `van den`, `de`, `ter`, `ten`) and a last name as ONE
`PERSON` span with layer `dutch_particle_name`, found by its own pattern. It
SHALL NOT turn ordinary text or an institution's name into a `PERSON`. The
irreversible `OpenAnonymiserAnonymizer` is out of scope.

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
first-name gazetteer shipped inside the package. Every entry SHALL carry a
reason, and the loader SHALL refuse an entry without one. A missing or
unreadable gazetteer SHALL be a hard error, not an empty list.

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

#### Scenario: The gazetteer ships inside the package

- **WHEN** wordsworth is installed without any detection-lists directory
- **THEN** the gazetteer is found inside the package and the rule runs; no
  deployment needs a file of its own for it

### Requirement: The gazetteer leaves out common words and stays out of lists_hash

A first name that is also a common capitalised word at sentence start (`Ton`,
`Wil`, `Bart`) SHALL NOT be a gazetteer entry. This costs recall on purpose: of
the 14 seeded first names in `eval/synthetic.py`, `Ton` and `Bart` stay
unmatched, a known and accepted miss traded for precision. The gazetteer file
SHALL NOT be part of `lists_hash`.

#### Scenario: A first name that is a common word is excluded

- **WHEN** the shipped gazetteer is listed
- **THEN** it holds none of `Ton`, `Wil` and `Bart`

#### Scenario: The excluded names stay unmatched

- **WHEN** `Ton` or `Bart` stands before a particle and a last name
- **THEN** no `PERSON` is detected by this rule, a known and accepted miss

#### Scenario: A gazetteer change does not alter lists_hash

- **WHEN** the gazetteer file changes
- **THEN** `lists_hash` is unchanged

### Requirement: The particle rule is not a deterministic detector

The rule SHALL NOT be a row in `detectors.DETECTORS`, so the anonymizer, the
pseudonymizer, `find_deterministic()`, the PII evaluation's deterministic layer
and the dataset column validation report what they reported before.

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
