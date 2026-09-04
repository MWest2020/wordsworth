# anonymization Specification

## Purpose
TBD - created by archiving change add-anonymization-adapter. Update Purpose after archive.
## Requirements
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

### Requirement: Versioned allow/deny lists refine detection

After detection, wordsworth SHALL apply git-versioned allow and deny lists:
a typed allow rule SHALL remove detections of that type whose value fully
matches the pattern; a typed deny rule SHALL add detections (layer `list`,
score 1.0). Where wordsworth does not control the substitution (the
irreversible service-side driver) only the deny list applies. The lists'
content hash SHALL be recorded in the de-identify audit record, and suppressed
detections SHALL be counted.

#### Scenario: Typed false positive is suppressed

- **WHEN** `allow.json` has `{"PERSON": ["^Jansen BV$"]}` and the detector tags
  `Jansen BV` as PERSON
- **THEN** the value is not redacted and `suppressed_by_list.PERSON == 1`

#### Scenario: Allow never crosses types

- **WHEN** the same allow rule exists and `Jansen BV` is detected as
  ORGANIZATION
- **THEN** the detection is kept

### Requirement: Feedback is recorded, not auto-applied

`POST /documents/{id}/feedback` SHALL append an audit record describing a
false positive or false negative by type and token, never by clear value, and
SHALL NOT modify any list.

#### Scenario: Feedback leaves lists untouched

- **WHEN** feedback is posted
- **THEN** an audit record exists and the list hash in the next run is unchanged

