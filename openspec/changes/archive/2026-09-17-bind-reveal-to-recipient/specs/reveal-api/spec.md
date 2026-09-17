## MODIFIED Requirements

### Requirement: Reveal authorisation and error semantics

The endpoint SHALL return 404 when the document or the grant is unknown, 403 when
the grant is revoked, expired, or scoped to a different document, and 409 when the
document has not been de-identified. A successful reveal SHALL be recorded as an
audited access event whose actor is the grant recipient, carrying the revealed
types and no clear value, leaving the audit chain verifiable.

Where caller authentication is enabled, the endpoint SHALL additionally refuse a
caller who is not the grant's recipient, with the same 403 and the same absence of
revealed text. A grant names who may reveal; until that name is checked, the grant
id is a bearer token, and a single leak — a log line, a ticket, a screenshot —
hands clear PII to whoever finds it.

The comparison SHALL be exact. A recipient is a label drawn from the same
vocabulary as the caller; two labels that merely resemble each other are not the
same label, and a reveal is the wrong place to be generous.

Where caller authentication is not enabled there is no caller to decide on, and
behaviour SHALL be unchanged — the documented tailnet-internal mode.

#### Scenario: A revoked grant is refused

- **WHEN** a reveal is requested with a revoked grant
- **THEN** the endpoint responds 403 and no text is revealed

#### Scenario: Reveal is audited

- **WHEN** a reveal succeeds
- **THEN** a `deanonymize` audit record is appended for that document with the
  grant recipient as actor and the revealed types, containing no clear values,
  and the audit chain still verifies

#### Scenario: A caller who is not the recipient is refused

- **WHEN** caller authentication is enabled and an authenticated caller presents a
  valid grant issued to a different recipient
- **THEN** the endpoint responds 403 and no text is revealed

#### Scenario: The recipient reveals normally

- **WHEN** caller authentication is enabled and the caller is the grant's recipient
- **THEN** the reveal proceeds exactly as it did before

#### Scenario: Without caller authentication nothing changes

- **WHEN** caller authentication is disabled
- **THEN** the grant is evaluated on status, expiry, document scope and domain
  only, as before
