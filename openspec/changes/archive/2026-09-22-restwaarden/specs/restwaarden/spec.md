## ADDED Requirements

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
