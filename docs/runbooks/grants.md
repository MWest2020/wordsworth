# Runbook: reveal grants

Grants gate the key-gated reveal endpoint per PII type. They are **shareable**
(hand the `grant_id` to whoever may reveal) and **revocable** (revoke and the
reveal stops working immediately). Every issue/revoke is recorded in the
key-lifecycle audit stream.

> **Auth caveat.** This is an operator/admin surface with **no caller
> authentication yet** — the API is tailnet-internal and the `grant_id` is a
> bearer capability (anyone holding it can reveal what it allows). A real auth
> model is a pending decision; treat `grant_id`s as secrets until then.

## Issue

CLI:
```sh
wordsworth grant issue --recipient auditor \
  --types PERSON,LOCATION \
  [--document <document-uuid>] \
  [--expires 2026-12-31T00:00:00+00:00]     # ISO-8601, MUST be timezone-aware
```
HTTP: `POST /grants` `{recipient, allowed_types, document_id?, expires_at?}` → 201
with the grant metadata (including `grant_id`). `--document` scopes the grant to a
single document (omit for any document). A naive/invalid `expires_at` → 400.

## Inspect
```sh
wordsworth grant show <grant_id>          # GET /grants/{id}
```

## Revoke
```sh
wordsworth grant revoke <grant_id>        # POST /grants/{id}/revoke  (idempotent)
```
After revocation, `POST /documents/{id}/reveal` with that grant returns 403.

## Use a grant to reveal
```sh
curl -XPOST $API/documents/<doc>/reveal -H 'content-type: application/json' \
  -d '{"grant_id":"<grant_id>","types":["PERSON"]}'
```
Only the granted types are revealed; every other type stays pseudonymised. The
access is audited (actor = grant recipient, plus the `grant_id`), never logging
clear values.

## Notes
- Grant routes mount only when the deployment runs in reversible mode (a grant
  store is configured). In the irreversible default they are absent.
- The key-lifecycle audit JSONL path is `WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH`
  (default under `/tmp`); mount a durable path for retention. (This stream is not
  yet WORM-exported like the document hash-chain.)
