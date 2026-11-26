## MODIFIED Requirements

### Requirement: Reveal authorisation and error semantics

`POST /documents/{document_id}/reveal` and `POST /documents/{document_id}/reveal.pdf`
SHALL answer every caller the grant does not cover with the uniform refusal:
status 403 with the body `{"detail": "grant not applicable"}`. A grant does not
cover the request when it is unknown, revoked, expired, scoped to a different
document, bound to a different domain, unscoped where the deployment does not
allow it, or presented by a caller who is not its recipient, and a grant never
covers a document that does not exist.

The domain binding SHALL be decided before any answer about the document's
deletion or supersession, for scoped and unscoped grants alike. Where a
verifiable credential gate is configured, it SHALL be decided after the grant
and the domain and before those answers too: a caller it rejects SHALL get 403
`vc rejected: ...`, as today, and hear nothing about deletion or supersession.

To a caller the grant covers and the credential gate (where configured) admits,
the endpoints SHALL answer 410 when the document is deleted, 409 naming the
surviving document when it is superseded, and 409 when it has not been
de-identified (for `reveal.pdf` also when it has no box map), in that order,
and 409 when the document has more distinct tokens than one reveal of the key
service allows. A successful reveal SHALL be recorded as an audited access
event whose actor is the grant recipient, carrying the revealed types and no
clear value, leaving the audit chain verifiable.

Where caller authentication is enabled, the endpoints SHALL refuse a caller who
is not the grant's recipient, with the same uniform refusal and the same absence
of revealed text. A grant names who may reveal; until that name is checked, the
grant id is a bearer token, and a single leak — a log line, a ticket, a
screenshot — hands clear PII to whoever finds it.

The comparison SHALL be exact. A recipient is a label drawn from the same
vocabulary as the caller; two labels that merely resemble each other are not the
same label, and a reveal is the wrong place to be generous.

With the key service's reveal driver, the grant, the domain and the credential
gate SHALL be decided by the key service before wordsworth reads anything
about the document, and the key service SHALL verify the caller's signed
identity itself. A caller without a signed identity wordsworth can forward to
the key service (an API key, the console cookie, authentication not enabled)
SHALL get 403 `{"detail": "reveal needs a signed identity"}`, before any read
and whatever the grant or the document; the recipient check SHALL never be
skipped. A document the key service has not seen SHALL get the uniform
refusal, also from a caller whose grant names it. When the key service cannot
be reached or answers otherwise than the contract allows, the endpoints SHALL
answer 503 `{"detail": "reveal unavailable"}` and SHALL NOT reveal in-process.

With the in-process driver (until the switch, and after a rollback), where
caller authentication is not enabled there is no caller to decide on: the
recipient check SHALL be skipped — the documented tailnet-internal mode — and
every other check, the order and the uniform refusal SHALL apply unchanged.

#### Scenario: A revoked grant is refused

- **WHEN** a reveal is requested with a revoked grant
- **THEN** the endpoint answers the uniform refusal and no text is revealed

#### Scenario: Reveal is audited

- **WHEN** a reveal succeeds
- **THEN** a `deanonymize` audit record is appended for that document with the
  grant recipient as actor and the revealed types, containing no clear values,
  and the audit chain still verifies

#### Scenario: A caller who is not the recipient is refused

- **WHEN** caller authentication is enabled and an authenticated caller presents a
  valid grant issued to a different recipient
- **THEN** the endpoint answers the uniform refusal and no text is revealed

#### Scenario: The recipient reveals normally

- **WHEN** caller authentication is enabled and the caller is the grant's recipient
- **THEN** the reveal proceeds exactly as it did before

#### Scenario: Without caller authentication nothing changes

- **WHEN** caller authentication is disabled and the in-process driver is
  active
- **THEN** the grant is evaluated on status, expiry, scope and domain, and the
  recipient is not checked

#### Scenario: Without a signed identity, through the key service

- **WHEN** the key service's reveal driver is active and a caller with an API
  key, the console cookie or no authentication reveals
- **THEN** the endpoint answers 403 `reveal needs a signed identity`, reads
  nothing about the document and reveals nothing

#### Scenario: The key service is unreachable

- **WHEN** the key service's reveal driver is active and the key service does
  not answer
- **THEN** the endpoint answers 503 `reveal unavailable`, reads nothing about
  the document and reveals nothing in-process

#### Scenario: A covered caller is told the document is not yet de-identified

- **WHEN** the grant's recipient reveals a registered document that has no
  anonymized text yet
- **THEN** the endpoint answers 409 and no text is revealed
