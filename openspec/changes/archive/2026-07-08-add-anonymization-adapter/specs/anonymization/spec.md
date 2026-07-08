## ADDED Requirements

### Requirement: Anonymizer driver protocol

Anonymization SHALL be accessed through an `Anonymizer` protocol that takes text
and returns the anonymized text plus a per-type replacement count. The pipeline
SHALL depend on the protocol, never on a concrete engine, so that a different
engine (e.g. OpenAnonymiser) can be substituted without pipeline changes.

#### Scenario: A custom driver is used when injected

- **WHEN** a caller injects an alternative object satisfying the `Anonymizer`
  protocol
- **THEN** the pipeline uses it for the anonymize step instead of the default

### Requirement: Deterministic PII detection

The interim `DeterministicAnonymizer` SHALL detect and irreversibly replace, with
typed placeholders, only high-precision deterministic PII: BSN (validated by the
elfproef), IBAN (validated by mod-97), and email addresses. A candidate that
fails its validation SHALL be left untouched.

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

### Requirement: Irreversible replacement

Replacement SHALL be irreversible: placeholders SHALL carry no mapping back to
the original value. Reversible handling is out of scope (pseudonymization).

#### Scenario: Placeholders are not reversible

- **WHEN** a value is replaced
- **THEN** the output contains only the typed placeholder, with no stored mapping
  from placeholder to original value
