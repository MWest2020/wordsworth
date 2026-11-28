## ADDED Requirements

### Requirement: Opening an original names a purpose, is audited and fails closed

Every opening of an original SHALL name a purpose from a fixed list and SHALL
be audited with that purpose. A wrapped key or sealed object that fails to
authenticate SHALL fail closed. Sealing SHALL record the document's domain on
first sight and refuse a different domain afterwards, as pseudonymising does.

#### Scenario: No purpose, no open

- **WHEN** an open names no purpose or one outside the list
- **THEN** it is refused with 422 and nothing is decrypted

#### Scenario: A tampered key fails closed

- **WHEN** the wrapped data key or the sealed object has been altered
- **THEN** the open is refused, no plaintext is returned, and the failure is
  audited

#### Scenario: Seal and open stay in separate modules within the line limit

- **WHEN** the service's originals routes are built
- **THEN** seal is in `api_originals.py` and open is in `api_open.py`, and
  every module of the change is at most 200 lines

#### Scenario: A sealed document keeps its domain

- **WHEN** a document first pseudonymised or sealed in domain A is sealed in
  domain B
- **THEN** the service answers 409 and changes nothing
