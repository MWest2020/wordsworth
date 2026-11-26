## ADDED Requirements

### Requirement: Pseudonymising returns tokens and fills the service's registry

The key service SHALL turn a document's (type, value) pairs into tokens, store
the encrypted values, and register each returned token for that document in
its own registry. The response SHALL contain tokens only. The registry SHALL be
written only by the service's own pseudonymise (and by the cutover's verified
copy), SHALL never lose a token when a document is pseudonymised again, and
SHALL record each document's domain on first sight and refuse a different
domain afterwards.

#### Scenario: Tokens only

- **WHEN** a batch of values is pseudonymised for a document
- **THEN** the response holds one token per value and no value

#### Scenario: The token is registered for that document

- **WHEN** a value is pseudonymised for document A
- **THEN** its token is in the registry for A and for no other document

#### Scenario: A document keeps its domain

- **WHEN** a document first pseudonymised in domain A is pseudonymised or
  sealed in domain B
- **THEN** the service answers 409 and changes nothing

### Requirement: Opening an original is audited and rate-limited

Every opening of an original SHALL name a purpose from a fixed list, SHALL be
audited with that purpose, and SHALL be subject to a rate limit per calling
service. A wrapped key or sealed object that fails to authenticate SHALL fail
closed.

#### Scenario: A burst is refused

- **WHEN** a calling service opens originals faster than its limit
- **THEN** the excess is refused with 429 and each refusal is audited

#### Scenario: No purpose, no open

- **WHEN** an open names no purpose or one outside the list
- **THEN** it is refused with 422 and nothing is decrypted

#### Scenario: A tampered key fails closed

- **WHEN** the wrapped data key or the sealed object has been altered
- **THEN** the open is refused, no plaintext is returned, and the failure is
  audited

### Requirement: Deleting a document removes its keys, tokens, orphaned values and scoped grants

Deleting a document in the key service SHALL destroy its data keys, remove its
registry rows, every encrypted value no other document is registered for and
every grant scoped to that document, and keep only a tombstone with the
document's id and domain. A value another
document still holds SHALL survive, also when that other document is being
pseudonymised at the same moment.

#### Scenario: A shared value survives

- **WHEN** a document is deleted while another document holds the same token
- **THEN** that token's encrypted value remains and the other document's
  registry row is untouched

#### Scenario: Deleted means unopenable

- **WHEN** a document's originals are opened after its deletion
- **THEN** the service answers 404 and decrypts nothing

#### Scenario: Grants scoped to the document go with it

- **WHEN** a document with a grant scoped to it and an unscoped grant is
  deleted
- **THEN** the scoped grant is gone, the unscoped one remains, and the answer
  reports one grant deleted

### Requirement: Only reveal returns a clear value

No route of the key service other than reveal SHALL return a clear value from
the mapping store, and reveal SHALL need a verified person.

#### Scenario: No value without a person

- **WHEN** a calling service uses every route of the service with only its
  service token
- **THEN** no response contains a clear value from the mapping store
