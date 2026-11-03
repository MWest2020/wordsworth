## ADDED Requirements

### Requirement: Originals are read and written through one seam

Code SHALL read an original only through `read_original` and write one only
through `write_original`. Given an originals store, these SHALL open and seal;
given a plain object store, they SHALL use the plain read and write, and the
plain read SHALL keep refusing a sealed object. The originals store SHALL be
usable wherever a plain object store is expected, for objects that are not
originals.

#### Scenario: A sealed original through the seam

- **WHEN** an original is written with `write_original` to an originals store
  and read back with `read_original`
- **THEN** the stored object is sealed and the read returns the original bytes

#### Scenario: A sealed object through a plain store

- **WHEN** `read_original` is given a plain object store holding a sealed object
- **THEN** `SealedObjectError` is raised and no bytes are returned

### Requirement: One Transit client per KEK name

The service SHALL build at most one Transit client per KEK name and share it
across its users.

#### Scenario: The same KEK name twice

- **WHEN** the transit factory is asked twice for the same KEK name
- **THEN** it returns the same client
