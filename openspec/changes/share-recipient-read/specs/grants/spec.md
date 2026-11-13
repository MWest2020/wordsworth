## ADDED Requirements

### Requirement: A document grant lets its recipient read that document

The recipient of a grant that is active, not expired and scoped to one document
SHALL be allowed to open the redacted PDF and the console page of that document
without being on the corpus-read list. The grant SHALL open nothing else: no
other document, no search, no list of documents, no dossier, no topic, no
export, and not the de-identified text over the API.

The recipient SHALL be matched by the same rule a reveal uses: the caller's
label equals the grant's recipient exactly, ignoring only surrounding
whitespace. The types a grant allows SHALL NOT matter: a grant at PPL 0 counts.

The decision SHALL be made in one place, used by the redacted-PDF route and by
the console document page. Every refusal SHALL be a 403 with the message the
corpus-read refusal gives today, so that an answer does not tell a caller
whether the document exists, was shared with somebody else, or was shared with
him and taken back.

A caller on the corpus-read list SHALL be unaffected, and where the corpus-read
list is empty (the scope is off) behaviour SHALL be unchanged.

#### Scenario: The recipient opens a shared document

- **WHEN** an issuer grants a caller who is not on the corpus-read list a
  document-scoped grant at PPL 0 on document D, and that caller requests the
  redacted PDF of D and the console page of D
- **THEN** both answer 200

#### Scenario: A document that was not shared is refused

- **WHEN** that caller requests the redacted PDF or the console page of another
  document in the same dossier
- **THEN** the answer is 403

#### Scenario: A third caller is refused

- **WHEN** a caller who is neither on the corpus-read list nor the recipient
  requests the redacted PDF or the console page of D
- **THEN** the answer is 403

#### Scenario: A revoked grant is refused

- **WHEN** the grant on D is revoked and its recipient requests D again
- **THEN** the answer is 403, on the next request

#### Scenario: An expired grant is refused

- **WHEN** the current time is at or past the grant's expiry
- **THEN** the recipient's request for D answers 403, while one second before
  the expiry it answered 200

#### Scenario: A grant without a document scope is not a share

- **WHEN** a caller who is not on the corpus-read list holds an active grant
  with no document scope, in a deployment that allows global grants, or on the
  name of the beheerder role
- **THEN** his request for any document's redacted PDF or console page answers
  403

#### Scenario: A similar label is not the recipient

- **WHEN** a caller whose label differs from the recipient only in case, or
  only by a prefix, requests D
- **THEN** the answer is 403

#### Scenario: Search stays closed

- **WHEN** the recipient of a grant on D requests `/console/search`,
  `/console`, `/console/documents`, `/console/dossier`, `/console/topics`,
  `/console/feedback`, `GET /documents/{D}/anonymized` or
  `/export/anonymized.zip`
- **THEN** each answers 403

#### Scenario: An unknown document is refused, not reported

- **WHEN** a caller who is not on the corpus-read list requests the redacted
  PDF of a document id that does not exist
- **THEN** the answer is 403 and not 404, as it is today

#### Scenario: A reader on the list is unaffected

- **WHEN** a caller on the corpus-read list requests a document, with or
  without a grant on it
- **THEN** he gets the answer he got before this change, including 404 for an
  unknown document

### Requirement: Only a grant that is in force on a live document counts as a share

A grant SHALL count as a share only while its document is live: a document
whose state is `deleted`, or a superseded copy, SHALL NOT be opened through a
grant, by the one rule the console uses to hide documents. A grant that names a
role SHALL count only while that role exists and is switched on, so that
switching a role off takes the reading away at once, as it takes the revealing
away.

The pseudonymisation domain of a grant SHALL NOT be part of this decision.

#### Scenario: A superseded copy is refused

- **WHEN** a caller holds an active grant on a document that has been
  superseded
- **THEN** his request for that document answers 403

#### Scenario: A deleted document is refused

- **WHEN** a shared document is deleted
- **THEN** the recipient's next request for it answers 403

#### Scenario: A role that is switched off takes the reading away

- **WHEN** a recipient holds a document-scoped grant naming a role, and that
  role is switched off
- **THEN** his request for the document answers 403, and 200 again after the
  role is switched back on, without any grant having changed
