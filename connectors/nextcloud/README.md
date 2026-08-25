# Nextcloud → Wordsworth connector (standalone, loosely coupled)

A **separate** document-source connector. It is deliberately **not** part of the
Wordsworth application or container image — it lives here at the repo top level,
imports nothing from the `wordsworth` package, and couples to Wordsworth **only**
through the public `POST /ingest` HTTP API.

```
Nextcloud  --WebDAV(PROPFIND/GET)-->  this connector  --HTTP POST /ingest-->  Wordsworth
```

Wordsworth therefore stays **source-agnostic**: it never knows about Nextcloud.
Any producer (this connector, NiFi per ADR-0001, a script, another team's
service) feeds documents the same way — through `/ingest`. That is the loose
coupling the architecture requires; an in-process `/ingest/nextcloud` endpoint
(the earlier approach) coupled the core to one source and was withdrawn
(`openspec/changes/archive/…-remove-nextcloud-from-core`).

> The **canonical** connector is owned by a separate agent. This file is a
> working handoff reference.

## Run

Runs as its own process / Kubernetes CronJob. Config via environment:

| Env | Meaning |
|---|---|
| `NEXTCLOUD_URL` | e.g. `https://cloud.example.org` |
| `NEXTCLOUD_USER` | Nextcloud user |
| `NEXTCLOUD_PASSWORD` | Nextcloud **app-password** (secret; WebDAV Basic auth only) |
| `NEXTCLOUD_FOLDER` | folder relative to the user's files root (default `/`) |
| `WORDSWORTH_URL` | e.g. `http://wordsworth.tail…:8000` |
| `WORDSWORTH_API_KEY` | optional; sent as `X-API-Key` when Wordsworth auth is enabled |

```sh
pip install httpx
NEXTCLOUD_URL=… NEXTCLOUD_USER=… NEXTCLOUD_PASSWORD=… NEXTCLOUD_FOLDER=/Woo \
WORDSWORTH_URL=http://wordsworth.tail…:8000 \
python connectors/nextcloud/nextcloud_connector.py
```

It lists PDFs under the folder (recursively) and POSTs each to `/ingest`.
Idempotency, de-identification, the pseudonyms-only index, and per-file outcome
counts are all Wordsworth's job (content-addressed, so re-runs only push new
bytes). Continue-on-failure; the Nextcloud password is never printed.

Only `httpx` + the standard library are required. No coupling to Wordsworth
internals — swap the source or the sink freely.
