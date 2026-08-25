## REMOVED Requirements

### Requirement: Pull documents from Nextcloud over WebDAV

Withdrawn from the core. A source-specific pull belongs in a standalone connector
that talks to Wordsworth only through the generic `POST /ingest`, not in the
Wordsworth package.

### Requirement: Nextcloud files flow through the existing straat

Withdrawn from the core. Sources feed the straat through the public `/ingest`
API; the core no longer contains Nextcloud-specific wiring.

### Requirement: Inert and safe when unconfigured

Withdrawn from the core along with the rest of the in-process Nextcloud coupling.
