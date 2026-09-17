## ADDED Requirements

### Requirement: The console carries its own assets

The console SHALL serve its fonts and stylesheet from its own origin and SHALL
NOT reference a third-party CDN.

This screen is where wordsworth's claim to sovereignty is demonstrated, and it is
also the screen people inspect. A page that fetches its letters from Google
refutes that claim in the network inspector, whatever the surrounding text says.

The asset subtree SHALL be reachable without a key, because the login page is
itself reachable without a key and a login screen rendered without its letters is
a broken door. The exemption SHALL cover that subtree only.

#### Scenario: No third-party origin appears in a rendered page

- **WHEN** any console page is rendered
- **THEN** it references no font or stylesheet host other than the console's own

#### Scenario: The stylesheet and the file it points at are both served

- **WHEN** the stylesheet is requested and a font URL inside it is followed
- **THEN** both are served, so a packaging regression that ships the CSS without
  the font files is caught

#### Scenario: The exemption is a subtree, not a blanket

- **WHEN** a path outside the asset subtree is requested without a key
- **THEN** it is refused as before
