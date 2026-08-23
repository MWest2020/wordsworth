## ADDED Requirements

### Requirement: Pull documents from Nextcloud over WebDAV

The system SHALL be able to list a Nextcloud folder over WebDAV (recursively) and
fetch each file's bytes, authenticating with a user + app-password used only for
transport auth. Listing SHALL return files (not collections) as paths relative to
the user's files root.

#### Scenario: List a folder and fetch a file

- **WHEN** a Nextcloud folder is listed
- **THEN** every file under it (including subfolders) is returned, directories are
  excluded, and each file's bytes can be fetched

### Requirement: Nextcloud files flow through the existing straat

Files pulled from Nextcloud SHALL be driven through the existing ingest+process
pipeline, so de-identification and the pseudonyms-only index are unchanged.
Ingestion SHALL be idempotent (a file whose content is already indexed is skipped)
and SHALL continue past a file that fails, reporting per-outcome counts. Only
supported document types (PDF) SHALL be ingested; others SHALL be skipped.

#### Scenario: Idempotent, fault-tolerant pull

- **WHEN** a folder containing a new PDF, a duplicate of an already-indexed PDF, a
  malformed PDF, and a non-PDF is pulled
- **THEN** the new PDF is ingested, the duplicate is skipped, the malformed one is
  reported failed without aborting the run, the non-PDF is skipped, and re-running
  ingests nothing new

### Requirement: Inert and safe when unconfigured

The Nextcloud coupling SHALL be inert when no Nextcloud is configured: the ingest
endpoint SHALL NOT be mounted and the app SHALL still start. The Nextcloud
app-password SHALL NOT appear in logs, responses, or the repository.

#### Scenario: No Nextcloud configured

- **WHEN** no Nextcloud URL/user/password is set
- **THEN** the `/ingest/nextcloud` endpoint is absent and the CLI reports that
  Nextcloud ingest is not configured
