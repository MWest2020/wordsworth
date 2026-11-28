## ADDED Requirements

### Requirement: The old tables are dropped by a separate command, only after the window

wordsworth's old key, mapping and grant tables SHALL be dropped only by a
command separate from the migration and the switch, and that command SHALL
refuse to run inside the verification window (configurable, default 7 days).

#### Scenario: Inside the window the command refuses

- **WHEN** the drop command runs before the verification window has passed
- **THEN** it refuses and every old table is still in place

#### Scenario: After the window the tables are dropped

- **WHEN** the drop command runs after the window
- **THEN** the old tables are dropped

#### Scenario: The migration never drops

- **WHEN** the migration or the switch runs
- **THEN** no old table is dropped

### Requirement: After the drop wordsworth's database user reads no key, mapping or grant

Once the old tables are dropped, wordsworth's database user SHALL be able to
read no key, mapping or grant table.

#### Scenario: A read after the drop fails

- **WHEN** wordsworth's database user reads a former key, mapping or grant table
  after the drop
- **THEN** the read fails
