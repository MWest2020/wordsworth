## ADDED Requirements

### Requirement: A share issues one grant per live document through the issuer gate

The system SHALL let a caller who may issue grants share a document, a topic
or a dossier with a recipient, at a privacy protection level or a role, with an
expiry, by issuing one document-scoped grant per live document in scope. Each
grant SHALL be issued by the function `POST /grants` uses and SHALL write its
own issue event to the key-lifecycle audit stream. The grants of one share
SHALL carry one share id and SHALL be issued in one transaction: all of them,
with their events, or none.

Who may share SHALL be decided by the issuer gate of `POST /grants` and by
nothing else: with caller authentication on, the labels the deployment names
as issuers. No role SHALL give the right to share. A refused caller SHALL get
403, and no grant and no audit event SHALL come into being.

The level SHALL default to PPL 0 and the expiry to 30 days from the moment of
sharing; a share SHALL always have an expiry. A share SHALL NOT issue a grant
without a document scope and SHALL NOT name the beheerder role.

A live document is one the console does not hide: not deleted and not a
superseded copy. A share is the documents it was issued for at that moment; a
document that joins the dossier or the topic later SHALL NOT become part of
it.

No message, page or audit event of a share SHALL contain a PII value from a
document.

#### Scenario: A dossier is shared

- **WHEN** an issuer shares a dossier of three live documents, one deleted
  document and one superseded copy with a recipient at PPL 1
- **THEN** three grants exist, one per live document, with the same share id,
  the recipient and the PPL 1 types, and the audit stream gained three issue
  events

#### Scenario: The defaults are the least

- **WHEN** an issuer shares a document and names only the recipient
- **THEN** the grant allows no types and expires 30 days later

#### Scenario: A caller who is not an issuer is refused

- **WHEN** a logged-in caller who is not an issuer label shares, whether or not
  he may read the corpus and whether or not he holds the beheerder role
- **THEN** the answer is 403, no grant exists and the audit stream gained no
  event

#### Scenario: A share that fails halfway issues nothing

- **WHEN** issuing the third of five grants of a share fails
- **THEN** none of the five grants exists and the audit stream holds no event
  of that share

#### Scenario: A share cannot appoint a beheerder

- **WHEN** an issuer shares at the role `beheerder`
- **THEN** it is refused before any grant is issued

#### Scenario: A later document is not shared

- **WHEN** a document is added to a dossier after the dossier was shared
- **THEN** no grant exists for the recipient on that document

### Requirement: Sharing a topic reads its members from the index or shares nothing

The members of a topic SHALL be read from the search index, where topic
membership lives, and only members that are live documents of the topic's
dossier SHALL get a grant. When the index cannot be reached, sharing a topic
SHALL be refused with a message that says so and that nothing was shared, and
no grant and no audit event SHALL come into being. Sharing a document or a
dossier SHALL NOT depend on the index.

#### Scenario: A topic is shared

- **WHEN** an issuer shares a topic whose index membership holds two live
  documents and a stale entry for a deleted one
- **THEN** two grants are issued

#### Scenario: The index is unreachable

- **WHEN** an issuer shares a topic while the index cannot be reached
- **THEN** the answer says the index is unreachable and nothing was shared, no
  grant exists and the audit stream gained no event

#### Scenario: A dossier is shared while the index is unreachable

- **WHEN** an issuer shares a dossier while the index cannot be reached
- **THEN** the share is issued as usual

### Requirement: A share is revoked as a whole

Revoking a share SHALL revoke every grant of that share that is still active,
each through the function that revokes a single grant and each with its own
revoke event naming the caller as actor. It SHALL be decided by the same issuer
gate. Revoking a share again SHALL change nothing and write no event. A grant
of another share, or of no share, SHALL NOT be touched.

#### Scenario: A share is revoked

- **WHEN** an issuer revokes a share of three grants
- **THEN** all three are revoked, the audit stream gained three revoke events,
  and a grant issued to the same recipient outside that share is still active

#### Scenario: Revoking twice writes nothing

- **WHEN** the same share is revoked a second time
- **THEN** no grant changes and the audit stream gained no event

#### Scenario: A non-issuer cannot revoke a share

- **WHEN** a caller who is not an issuer label revokes a share
- **THEN** the answer is 403 and every grant of the share is still active
