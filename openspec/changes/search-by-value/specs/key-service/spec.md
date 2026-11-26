## ADDED Requirements

### Requirement: The key service translates a value to its token for an authorised caller

The key service SHALL, for a caller who is the recipient of an active,
unexpired, unscoped grant that allows a PII type (itself or through its
role), normalise a typed value with the ingest normalisation profile and
return the tokens it yields under every active key version of that type and
domain. It SHALL refuse the translation with 403 for any other
caller, and SHALL return only tokens, never the value.

#### Scenario: An authorised caller gets the token ingest produced

- **WHEN** a caller allowed PERSON looks up `jansen` and the corpus was
  pseudonymised with `Jansen`
- **THEN** the returned tokens include the token found in that corpus

#### Scenario: A caller without the right is refused

- **WHEN** a caller with no unscoped grant for PERSON looks up a value, also
  when they hold a grant for PERSON scoped to one document, or a role that
  allows PERSON only through a group
- **THEN** the key service answers 403 and returns no token

#### Scenario: A revoked grant stops translating

- **WHEN** the grant that gave a caller PERSON is revoked
- **THEN** the next lookup by that caller is refused

### Requirement: A value lookup is audited without the value

Every value lookup, granted or refused, SHALL write an audit record holding
the caller, the type, the outcome and, when granted, the tokens and the number
of matching documents, and SHALL NOT hold the value or a hash of it. The value
SHALL NOT appear in any log of the key service.

#### Scenario: The audit holds the token, not the value

- **WHEN** a sentinel value is looked up
- **THEN** the audit record carries the token and the outcome, and no log or
  audit record contains the sentinel
