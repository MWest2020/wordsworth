---
status: draft
last_reviewed: 2026-09-04
---

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
single document and is **required by default** — see the next section. A
naive/invalid `expires_at` → 400.

## Global (unscoped) grants are off by default

A grant without a document scope authorizes reveal on **every** document. That is
a legitimate bulk-reveal capability, but too broad to hand out by forgetting a
flag, so it is gated:

| `WORDSWORTH_ALLOW_GLOBAL_GRANTS` | Issue without `--document` | An existing unscoped grant |
|---|---|---|
| unset / `false` (default) | 400 `document_id required (global grants are not allowed)` | authorizes nothing (reveal → 403) |
| `true` | 201 | authorizes any document |

The gate is enforced in `grants.authorize()`, not only at issue, so a grant
created before the gate — or written straight into the database — is covered too.
Turning it on is a deployment decision, visible in the deployment's configmap:

```sh
WORDSWORTH_ALLOW_GLOBAL_GRANTS=true   # bulk reveal across documents
```

Prefer a scoped grant per document; reach for the flag only for an actual
cross-document task, and turn it off again afterwards.

## Issue by Privacy Protection Level (PPL)

Instead of listing types, issue at a level; the server expands it through the
PII category registry (`pii_categories.py`) and stores plain `allowed_types`.

| PPL | Reveals | AVG basis | Typical holder (per the NORA target architecture) |
|---|---|---|---|
| 0 | nothing — placeholders only | — | data teams, external parties |
| 1 | ordinary personal data (PERSON, LOCATION, BSN, IBAN, EMAIL, …) | Art. 6 | functional administrators |
| 2 | PPL 1 + special categories (GEZONDHEID, RELIGIE, ETNICITEIT, BIOMETRIE, …) | Art. 6 + 9 | privacy officers |
| 3 | everything incl. criminal data (STRAFRECHTELIJK) | Art. 6 + 9 + 10 | FG, emergency procedures |

```sh
wordsworth grant issue --recipient privacy-officer --ppl 2 [--document <uuid>]
```
HTTP: `POST /grants` `{recipient, ppl}` — `ppl` and `allowed_types` are mutually
exclusive (422 on both or neither). The response reports `ppl` whenever the
stored type set equals a level exactly. Reveal responses add `by_legal_basis`
(the revealed/withheld types grouped under Art. 6/9/10) and the reveal audit
record carries the categories touched (`c1`/`c2`/`c3`), never values. A type the
registry does not know is treated as Art. 6 (`c1`) and is *not* granted
implicitly by any level.

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
- An unscoped ("global") grant needs `WORDSWORTH_ALLOW_GLOBAL_GRANTS=true`; see
  above. Default is denied, at issue and at authorize.
- The key-lifecycle audit JSONL path is `WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH`
  (default under `/tmp`); mount a durable path for retention. (This stream is not
  yet WORM-exported like the document hash-chain.)
