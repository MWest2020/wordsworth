## ADDED Requirements

### Requirement: A key user shares a document, a topic or a dossier from the console

The console SHALL let a caller allowed to issue grants share a document, a
topic or a dossier with a recipient at a privacy protection level or a role, with
an expiry, by issuing one grant per live document in scope through the same
issuer gate and audit as the API, grouped under one share that can be revoked as
a whole. The level SHALL default to PPL 0 and the expiry to 30 days.

#### Scenario: A dossier is shared

- **WHEN** a beheerder shares a dossier at PPL 1 with a recipient
- **THEN** one grant per live document is issued under one share and the page lists the redacted PDF links

#### Scenario: A caller without the right is refused

- **WHEN** a caller who is neither beheerder nor an issuer label shares
- **THEN** the answer is 403 and no grant is issued

#### Scenario: A share is revoked

- **WHEN** the sharer revokes the share
- **THEN** every grant of that share is revoked
