## MODIFIED Requirements

### Requirement: Deterministic PII detection

The interim `DeterministicAnonymizer` SHALL detect and irreversibly replace, with
typed placeholders, only high-precision deterministic PII: BSN (validated by the
elfproef), IBAN (validated by mod-97), email addresses, and Dutch postcodes. A
candidate that fails its validation SHALL be left untouched.

A detector MAY carry a **context rule** that rejects a match on the grounds of
what surrounds it, where the value alone cannot decide. The postcode detector
carries exactly one: a postcode directly preceded by `Postbus <number>` is the
contact address of an organisation, not a household, and SHALL be left readable —
redacting it makes a decision unreadable without protecting anyone. The rule SHALL
be defined once, in the shared detector table, so that every path that replaces
PII applies the same exceptions.

A context rule SHALL be written so that text rewritten by detectors running
earlier cannot change its answer. The detectors run in sequence and each replaces
values with placeholders of a different length, so a rule that merely scans a
window backwards would have a reach that shifts with whatever happened to precede
the match — the same rule, on the same source, answering differently depending on
how many email addresses came before. Requiring the marker to sit **directly**
before the match is what rules that out: if nothing stood between them in the
source, nothing was replaced there either; and an inserted placeholder can only
break such a match, never create one.

#### Scenario: Valid BSN is replaced

- **WHEN** the text contains a 9-digit number that passes the elfproef
- **THEN** it is replaced by `[BSN]` and the BSN count increments

#### Scenario: Invalid BSN is left untouched

- **WHEN** the text contains a 9-digit number that fails the elfproef
- **THEN** it is not replaced and the BSN count does not increment

#### Scenario: Valid IBAN is replaced

- **WHEN** the text contains an IBAN-shaped string that passes mod-97
- **THEN** it is replaced by `[IBAN]` and the IBAN count increments

#### Scenario: Email is replaced

- **WHEN** the text contains an email address
- **THEN** it is replaced by `[EMAIL]` and the email count increments

#### Scenario: A PO box keeps its postcode

- **WHEN** the text contains `Postbus 250, 6800 GD Arnhem`
- **THEN** the postcode is left readable and the postcode count does not increment

#### Scenario: A street address loses its postcode

- **WHEN** the text contains `Brinklaan 35, 1404 GZ Bussum`
- **THEN** the postcode is replaced and the postcode count increments

#### Scenario: An earlier replacement does not change the answer

- **WHEN** the same PO box line is de-identified twice, once with an email address
  on the line before it and once without
- **THEN** the postcode is left readable in both cases

#### Scenario: A marker that is not directly before the postcode does not count

- **WHEN** the text contains `Postbus 16005` and a line of other text before
  `3500 DA`
- **THEN** the postcode is replaced, because the rule requires the marker directly
  before the match
