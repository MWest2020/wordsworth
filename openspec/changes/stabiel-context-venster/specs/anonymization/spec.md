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

## ADDED Requirements

### Requirement: Context rules see the source text

A context rule SHALL be evaluated against the text as it entered the deterministic
pass, at the position the match holds in that text — never against the partially
rewritten text produced by detectors that ran earlier.

The detectors run in sequence, and each one replaces values with placeholders of a
different length than the values they replace. A context rule that looks backwards
over the working text therefore has a reach that shifts with whatever happened to
precede it: the same rule, on the same source, answers differently depending on how
many email addresses came before. Such a rule cannot be reasoned about and cannot
be tested for what it promises, and the accident cuts both ways — a household
postcode can be kept because a replacement pulled the word `Postbus` into reach.

#### Scenario: A replacement before the match does not change the answer

- **WHEN** the same PO box line is de-identified twice, once with an email address
  on the preceding line and once without
- **THEN** the postcode is left readable in both cases

#### Scenario: A replacement cannot pull a marker into reach

- **WHEN** a street-address postcode has `Postbus 6000` in the source text further
  back than the context rule reaches, and an earlier replacement shortens the text
  in between
- **THEN** the postcode is still replaced
