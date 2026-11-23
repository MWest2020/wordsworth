# reveal-api Specification

## Purpose

The door through which an identity comes back: key-gated, per type, and legible
about what it did not show.

The interesting requirement is the **legible placeholder view**. A redacted
document that hides the fact that it is redacted misleads the reader about what
they have. Showing what was withheld, and **reporting the types per legal basis**,
turns a reveal from a binary into something a case handler can reason about — and
something they can ask for more of, on the right ground.

Authorisation and error semantics are specified precisely because the difference
between "you may not" and "there is nothing here" is itself information.

## Requirements

### Requirement: Key-gated per-type reveal endpoint

The API SHALL expose `POST /documents/{document_id}/reveal` accepting a grant id
and an optional list of PII types. It SHALL reveal only the types the grant
authorises for that document; every other type SHALL remain pseudonymised. When
no types are given, it SHALL reveal exactly the types the grant allows. The
response SHALL report the revealed types and the requested-but-withheld types.
The endpoint SHALL be mounted only when a key provider and grant store are
configured.

#### Scenario: Only the granted type is revealed

- **WHEN** a reveal is requested with a grant that allows one PII type but the
  request asks for two
- **THEN** the response text contains the original for the granted type, the
  other type stays pseudonymised, and the response lists the granted type as
  revealed and the other as withheld

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
de-identified (for `reveal.pdf` also when it has no box map), in that order. A successful reveal SHALL be recorded as an audited access
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

Where caller authentication is not enabled there is no caller to decide on: the
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

- **WHEN** caller authentication is disabled
- **THEN** the grant is evaluated on status, expiry, scope and domain, and the
  recipient is not checked

#### Scenario: A covered caller is told the document is not yet de-identified

- **WHEN** the grant's recipient reveals a registered document that has no
  anonymized text yet
- **THEN** the endpoint answers 409 and no text is revealed

### Requirement: Legible placeholder view

`GET /documents/{id}/anonymized` SHALL accept `view=legible`, rendering each
distinct keyed token as a numbered, Dutch-labelled placeholder
(`[PERSOON 1]`, `[ADRES 2]`), numbered per type in order of first occurrence
within the document, with a `legend` mapping each placeholder back to its
token. The default view SHALL remain the stored token text. The stored text and
the index SHALL not change.

#### Scenario: Same token, same ordinal

- **WHEN** `[PERSON:3fa9c2d1]` occurs twice and `[PERSON:9b0e11aa]` once
- **THEN** the legible view shows `[PERSOON 1]` twice and `[PERSOON 2]` once,
  and the legend has exactly two PERSOON entries

#### Scenario: Default is unchanged

- **WHEN** the endpoint is called without `view`
- **THEN** the response equals today's token text

### Requirement: Reveal reports types per legal basis

The reveal response SHALL, in addition to `revealed_types` and
`withheld_types`, group both sets under their AVG legal basis
(`by_legal_basis: {"Art. 6": {...}, "Art. 9": {...}, "Art. 10": {...}}`). The
reveal audit record SHALL carry the set of categories touched and never a clear
value.

#### Scenario: Grouping mirrors the flat sets

- **WHEN** a reveal returns `revealed_types` and `withheld_types`
- **THEN** the union of all types in `by_legal_basis` equals the union of the two
  flat sets, each type under exactly one basis

### Requirement: A reveal decides the grant before it reads the document

Both reveal endpoints SHALL resolve the grant and run `grants.authorize()` on its
recipient (where caller authentication is enabled), revocation, expiry and
document scope, including whether an unscoped grant is allowed, before reading
anything about the document: its state, its row, whether and by which document it
is superseded, its domain, its box map, its text or its pseudonyms. A request
whose grant fails there SHALL get the uniform refusal without any of those reads.
The domain binding needs the document's registration record and SHALL be decided
after it, with the same refusal when it fails.

Authentication (401) and request validation (422 for a malformed document id or
body) SHALL keep coming first; they say nothing about the corpus.

#### Scenario: A grant that does not apply reads nothing about the document

- **WHEN** a reveal is requested, on either endpoint, with an unknown grant id, a
  revoked grant, an expired grant, a grant scoped to another document, or (with
  caller authentication enabled) a grant issued to another recipient
- **THEN** the endpoint answers the uniform refusal and no database statement
  reads the document, its audit records, its box map, its anonymized text or its
  pseudonyms during the request

#### Scenario: A grant bound to another domain is refused after the lookup

- **WHEN** the recipient of a grant bound to the default domain reveals, on either
  endpoint, a document registered in another domain
- **THEN** the endpoint answers the uniform refusal and no text is revealed

### Requirement: A refused reveal looks the same whatever the cause

To a caller the grant does not cover, both reveal endpoints SHALL give the same
answer — the same status, the same body and the same content type for the same
request headers — for an unknown grant, a grant that does not apply, an unknown
document, a superseded document, a deleted document, and an existing live
document outside the grant's scope. Such a caller SHALL NOT learn from a reveal
whether a document exists, whether it is superseded or by which document, or
whether it is deleted.

#### Scenario: An unknown document and a document outside the scope look alike

- **WHEN** a caller with caller authentication enabled presents a grant issued to
  another recipient, once for an unknown document id and once for an existing
  live document, on each endpoint
- **THEN** both answers are the uniform refusal, with identical status and body

#### Scenario: A superseded document does not name its survivor

- **WHEN** a caller the grant does not cover reveals a superseded document, on
  either endpoint
- **THEN** the answer is the uniform refusal and the body contains neither the
  survivor's id nor the word "superseded"

#### Scenario: A deleted document is not announced

- **WHEN** a reveal is requested on a deleted document, on either endpoint, with
  a grant id that does not exist, with the grant the deletion removed, or with a
  grant issued to another recipient
- **THEN** the answer is the uniform refusal, not 410

#### Scenario: An unknown grant is not a 404

- **WHEN** a reveal is requested with a grant id that does not exist, on an
  existing document and on an unknown one, on either endpoint
- **THEN** both answers are the uniform refusal

#### Scenario: A grant that would cover any document does not cover a missing one

- **WHEN** the deployment allows global grants and the recipient of an unscoped
  grant reveals a document id that does not exist, on either endpoint
- **THEN** the answer is the uniform refusal, not 404

#### Scenario: All causes give one answer

- **WHEN** a caller the grant does not cover sends, on one endpoint and with the
  same headers, a reveal for each of: an unknown grant, a revoked grant, an
  expired grant, a grant scoped to another document, a grant issued to another
  recipient, an unknown document, a superseded document and a deleted document
- **THEN** every answer has the same status, the same body and the same content
  type

### Requirement: Only a covered caller learns supersession or deletion

A reveal endpoint SHALL tell a caller that a document is superseded, which
document survives it, or that it is deleted only when the grant covers that
caller for that document, its domain included, and the credential gate (where
configured) admits the caller.

#### Scenario: The recipient of a grant on a copy is told the survivor

- **WHEN** the recipient of a grant scoped to a superseded document reveals it,
  on either endpoint
- **THEN** the endpoint answers 409 naming the surviving document, and nothing is
  revealed

#### Scenario: A covered caller is told the document is deleted

- **WHEN** a caller holding a grant that survives the deletion and covers the
  document (an unscoped grant where the deployment allows it, or a grant under a
  global role) reveals a deleted document, on either endpoint
- **THEN** the endpoint answers 410 and nothing is revealed

#### Scenario: An unscoped grant from another domain hears nothing about deletion or supersession

- **WHEN** the recipient of an unscoped grant bound to domain A — allowed because
  the deployment allows global grants, or because the grant is under a global
  role — reveals, on either endpoint, a deleted document and a superseded
  document registered in domain B
- **THEN** each answer is the uniform refusal, never 410 and never 409

#### Scenario: A covered caller without a required credential hears nothing about the document

- **WHEN** a verifiable credential is required and the recipient of a grant that
  covers a superseded or a deleted document reveals it, on either endpoint,
  without a valid credential
- **THEN** the endpoint answers 403 `vc rejected: ...`, never 409 or 410, and
  nothing is revealed

#### Scenario: A grant removed by the deletion no longer covers

- **WHEN** the former recipient of a document-scoped grant reveals that document
  after it was deleted, with that grant's id, on either endpoint
- **THEN** the answer is the uniform refusal

### Requirement: A refused reveal leaves no trace of its cause

A refused reveal SHALL append no record to the document audit chain and no event
to the key-lifecycle stream. It SHALL NOT emit a log line, a metric label or an
error detail that names the cause of the refusal, the document's state or
existence, or a survivor id. Diagnosing a refusal SHALL go through routes with
their own gate (`GET /grants/{id}` for a reader or issuer, the document routes
behind corpus read), not through the reveal endpoints or their logs.

#### Scenario: A refusal writes no audit record

- **WHEN** a reveal is refused, on either endpoint, for any of the causes of the
  uniform refusal
- **THEN** the number of document audit records and of key-lifecycle events is
  the same before and after the request, and the audit chain still verifies

#### Scenario: A refusal logs nothing about its cause

- **WHEN** a reveal is refused, on either endpoint, for an unknown document, a
  superseded document, a deleted document and a document outside the grant's
  scope, while the application's log records are captured
- **THEN** no captured record contains a survivor's id, the words "unknown",
  "superseded" or "deleted", or the document's state, and the captured records
  are the same for every case apart from the document id in the request
