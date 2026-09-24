## ADDED Requirements

### Requirement: A superseded document leaves its dossiers as a recorded act

Superseding a document SHALL remove each of its dossier memberships through the
same recorded removal as any other, with actor `dedupe`. Before that, it SHALL
add every membership the surviving document does not already hold, so no
dossier loses a document it contained.

#### Scenario: The survivor already holds the membership

- **WHEN** a copy is superseded and the survivor is in the same dossier
- **THEN** the copy's membership is removed, recorded, and the dossier count
  drops by one

#### Scenario: Only the copy was in a dossier

- **WHEN** a copy is superseded and only the copy was in some dossier
- **THEN** the survivor is added to that dossier before the copy is removed
