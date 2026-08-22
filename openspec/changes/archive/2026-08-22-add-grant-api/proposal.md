## Why

Reveal grants (shareable, revocable, per-PII-type) existed only as code/DB
objects — there was no way for an operator to issue, inspect, or revoke one
without writing Python. That makes the "shareable + revocable" property
theoretical. This adds the operator surface (HTTP + CLI) that makes grants usable
in practice.

## What Changes

- **`POST /grants`** — issue a grant `{recipient, allowed_types, document_id?,
  expires_at?}`. `expires_at` is ISO-8601 and must be timezone-aware (a naive or
  malformed value is a 400; a malformed `document_id` is a 400). Returns the grant
  metadata (201). Recorded in the key-lifecycle audit stream via `issue_grant`.
- **`GET /grants/{grant_id}`** — inspect a grant (status/types/doc/expiry). 404 if
  unknown.
- **`POST /grants/{grant_id}/revoke`** — revoke (idempotent). 404 if unknown.
- These mount only when a grant store is configured (same signal as the reveal
  route); absent otherwise, so the default deployment is unchanged.
- **CLI**: `wordsworth grant issue|show|revoke`.
- Config `WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH` for the audit JSONL sink (default
  under /tmp); `create_app` gained an optional `key_audit` for injection/tests.

**Auth (explicitly deferred):** this is an operator/admin surface with NO caller
authentication yet — the API is tailnet-internal and the returned `grant_id` is a
bearer capability. A real auth model is a pending decision, documented on the
endpoint and in the runbook; not solved here.

## Capabilities

### Modified Capabilities
- `grants`: grants can be issued, inspected, and revoked over HTTP + CLI; every
  issue/revoke is audited to the key-lifecycle stream; responses carry no key
  material or clear PII; revocation is enforced by the existing `authorize`
  (a revoked grant reveals nothing).

## Impact

- Code: `api.py` (3 routes + 2 pydantic models + `key_audit` param), `client.py`
  (`grant` subcommands), `config.py` (audit path). No schema change; no new dep.
- Tests: local grant CRUD + 400s + route-absence + CLI arg/payload shaping;
  DB-integration proving issue→revoke gates the reveal endpoint (403). 244 local.
- Runbook `docs/runbooks/grants.md`.
