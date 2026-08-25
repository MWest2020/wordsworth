## Why

The `nextcloud-ingest` capability was built IN-PROCESS inside the Wordsworth
application: a `nextcloud_source` module, a `POST /ingest/nextcloud` route, config
properties, and a CLI subcommand. That couples the core to one specific document
source — Wordsworth ends up "knowing about" Nextcloud/WebDAV. The architecture
requires the opposite: **everything loosely coupled**. Wordsworth already exposes
a generic `POST /ingest`; any source (Nextcloud, NiFi per ADR-0001, a script,
another team's service) must feed documents through that public API and live
outside the core. A source-specific connector does not belong in the Wordsworth
package.

## What Changes

- **Withdraw `nextcloud-ingest` from the core.** Remove `nextcloud_source.py`, the
  `/ingest/nextcloud` route, the `WORDSWORTH_NEXTCLOUD_*` config, the
  `ingest-nextcloud` CLI subcommand, their tests, and the runbook. Wordsworth
  returns to being source-agnostic behind the generic `/ingest`.
- **Preserve the pull logic as a standalone, decoupled connector** at top-level
  `connectors/nextcloud/` — a self-contained script that reads Nextcloud over
  WebDAV and POSTs to Wordsworth's public `/ingest`, importing nothing from the
  package and shipping outside the app image. The canonical connector is owned by
  a separate agent; this is a handoff reference.
- **Untouched:** the generic `/ingest`, reversible pseudonymisation, reveal,
  grants, reprocess/backfill, export, and the opt-in `api-key-auth` middleware.

## Capabilities

### Removed Capabilities
- `nextcloud-ingest`: withdrawn from the core to keep Wordsworth source-agnostic;
  the equivalent is a standalone connector that feeds documents through the public
  `/ingest` API.

## Impact

- Code: delete `nextcloud_source.py` + its tests + runbook; remove the route from
  `api.py`, the properties from `config.py`, the subcommand from `client.py`, and
  the tests from `test_client.py`. Add `connectors/nextcloud/` (not part of the
  package/image). No behaviour change to any remaining endpoint. Suite stays green.
