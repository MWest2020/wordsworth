## ADDED Requirements

### Requirement: Een gepseudonimiseerde waarde staat nergens anders meer letterlijk in het document

When a value has been replaced by a pseudonym token in a document, that value
SHALL NOT remain elsewhere in the stored text of that same document, including
inside a longer string such as a web address, a file name or an e-mail address.

A value that was judged to be personal data does not stop being personal data
because it sits inside another word. `Eazwind` was replaced as an organisation
name in the letterhead and stayed inside `www.eazwind.nl` four lines down; that
is not a second decision, it is a missed first one.

Matching SHALL be case-insensitive and SHALL have a minimum length, because a
short value is a substring of ordinary language. The minimum SHALL be chosen by
measurement on the evaluation corpus and recorded with that measurement.

#### Scenario: A name survives inside a web address

- **WHEN** a value replaced as ORGANIZATION also occurs inside a URL in the same
  document
- **THEN** that occurrence is replaced as well

#### Scenario: A short value does not eat ordinary language

- **WHEN** a replaced value is shorter than the configured minimum
- **THEN** no substring replacement is made for it, and the run reports that it
  was skipped

### Requirement: Een straat met huisnummer is een adres

Detection SHALL treat a Dutch street name followed by a house number as an
address, also when no postcode accompanies it.

In a Woo file about a building permit the building is the case: from an address
to an owner is one land-registry lookup. The existing pattern found the postcode
and the place name and left `Industrieweg 23a` standing, which is the half that
identifies.

The pattern SHALL be anchored on street-like endings and SHALL NOT be a general
"capitalised word followed by a number", which would swallow `Artikel 5` and
`bijlage 3`.

#### Scenario: A street with a number is detected without a postcode

- **WHEN** a document contains `Amsterdamsestraatweg 65a` and no postcode nearby
- **THEN** it is detected as an address

#### Scenario: A legal reference is not an address

- **WHEN** a document contains `Artikel 5` or `bijlage 3`
- **THEN** neither is detected as an address

### Requirement: Het gat is gemeten voordat het gedicht heet

The effect SHALL be measured on the evaluation corpus, where the seeded values
are known, and the number SHALL be recorded with its date alongside the existing
measurements.

Without a number, "detection improved" is a feeling, and this is the part of the
system where a feeling is the least useful thing to have.

#### Scenario: The measurement is repeatable

- **WHEN** the evaluation corpus is generated and processed
- **THEN** the count of seeded values surviving into the stored text is reported
