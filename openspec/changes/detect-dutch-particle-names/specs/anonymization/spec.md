## ADDED Requirements

### Requirement: A name with a Dutch particle is one person

Detection SHALL treat a first name, a Dutch particle and a last name as ONE
`PERSON` span. The particles include `van`, `de`, `ter`, `ten` and `van der`;
a particle of several words is one particle.

What identifies a person is the whole name. Detecting the first name and the
last name apart leaves the particle readable or yields several tokens for one
person, and a name missed altogether stays in clear in the anonymised text. The
pilot read of the Gooise Meren dossier found exactly that: a full name shaped
`<first name> ter <last name>` left in a meeting agenda.

The rule SHALL NOT turn ordinary text into a name: a particle between words that
are not a name SHALL NOT yield a `PERSON`.

#### Scenario: A name with each particle is one PERSON

- **WHEN** a synthetic name is built with each of `van`, `de`, `ter`, `ten` and
  `van der` between a first name and a last name
- **THEN** each is detected as one `PERSON` span covering the whole name

#### Scenario: No part of the name stays readable

- **WHEN** a document containing such a name is de-identified
- **THEN** neither the first name, the particle nor the last name appears in the
  output

#### Scenario: A lowercase particle in ordinary text is not a name

- **WHEN** a sentence contains `de` or `van` between ordinary lowercase words
- **THEN** no `PERSON` is detected
