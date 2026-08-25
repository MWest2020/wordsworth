## 1. Remove from core

- [x] 1.1 Delete `src/wordsworth/nextcloud_source.py` + its 2 tests + runbook.
- [x] 1.2 Remove the `/ingest/nextcloud` route from `api.py`.
- [x] 1.3 Remove `WORDSWORTH_NEXTCLOUD_*` properties from `config.py`.
- [x] 1.4 Remove the `ingest-nextcloud` subcommand from `client.py` + its tests.

## 2. Preserve loosely-coupled

- [x] 2.1 `connectors/nextcloud/nextcloud_connector.py` — standalone; couples to
  Wordsworth ONLY via public `POST /ingest`; imports nothing from the package.
- [x] 2.2 `connectors/nextcloud/README.md` explains the loose coupling + handoff.

## 3. Gate

- [x] 3.1 Suite green; `/ingest/nextcloud` gone; generic `/ingest` + api-key-auth
  intact.
- [x] 3.2 CI green + `openspec validate`.
