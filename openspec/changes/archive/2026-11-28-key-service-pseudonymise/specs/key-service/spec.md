## ADDED Requirements

### Requirement: Pseudonymising returns tokens and fills the service's registry

The key service SHALL turn a document's (type, value) pairs into tokens, store
the encrypted values, and register each returned token for that document in
its own registry. The response SHALL contain tokens only. The registry SHALL be
written only by the service's own pseudonymise (and by the cutover's verified
copy), SHALL never lose a token when a document is pseudonymised again, and
SHALL record each document's domain on first sight and refuse a different
domain afterwards. A batch SHALL hold at most the configured number of items.

#### Scenario: Tokens only

- **WHEN** a batch of values is pseudonymised for a document
- **THEN** the response holds one token per value and no value

#### Scenario: The token is registered for that document

- **WHEN** a value is pseudonymised for document A
- **THEN** its token is in the registry for A and for no other document

#### Scenario: A document keeps its domain

- **WHEN** a document first pseudonymised in domain A is pseudonymised in
  domain B
- **THEN** the service answers 409 and changes nothing

#### Scenario: A batch over the cap is refused

- **WHEN** a batch holds more items than the configured maximum
- **THEN** the service answers 422 and registers nothing

### Requirement: Only reveal returns a clear value

No route of the key service other than reveal SHALL return a clear value from
the mapping store, and reveal SHALL need a verified person.

#### Scenario: No value without a person

- **WHEN** a calling service uses every route of the service with only its
  service token
- **THEN** no response contains a clear value from the mapping store
