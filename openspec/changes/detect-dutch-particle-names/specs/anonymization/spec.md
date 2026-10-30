## ADDED Requirements

### Requirement: A name with a Dutch particle is one person

Detection SHALL treat a first name, a Dutch particle and a last name as ONE
`PERSON` span. The particles are `van`, `de`, `ter`, `ten` and `van der`; a
particle of several words is one particle. The rule is its own deterministic
pattern, not a widening of spans another layer found, and its detections carry
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

- **WHEN** a synthetic name is built with each of `van`, `de`, `ter`, `ten` and
  `van der` between a first name and a last name
- **THEN** each is detected as one `PERSON` span covering the whole name

#### Scenario: The detection carries its own layer name

- **WHEN** such a name is detected
- **THEN** the detection's layer is `dutch_particle_name`

#### Scenario: No part of the name stays readable

- **WHEN** a document containing such a name is de-identified
- **THEN** neither the first name, the particle nor the last name appears in the
  output

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
