# Change: key-audit-in-postgres

## Why

The key-lifecycle stream is where wordsworth records the facts that decide who
may see what without touching a document: grants issued and revoked, roles
created and narrowed, dossiers renamed, keys rotated. The spec promises it is
**append-only**. It says nothing about surviving a restart, and in production it
does not.

Measured on 2026-09-23 in the running api pod:

- the stream is `/tmp/wordsworth-key-lifecycle.jsonl`
  (`WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH` is unset, so the default applies);
- `/tmp` is an **`emptyDir`** — wiped every time the pod restarts;
- the file held **exactly one event**: a grant revoked that morning. Every
  grant, role change and rename before the last restart (2026-09-22 17:59) is
  gone and cannot be recovered.

"Append-only" was true and meaningless: nothing was ever rewritten, because
nothing ever lasted long enough.

Mapping every writer made it worse, not better:

| writer | reaches the stream? |
|---|---|
| grant issue / revoke (API) | yes — to `/tmp` |
| role changes (API, console) | yes — to `/tmp` |
| **dossier rename** (`wordsworth-dossier-hernoem`, the only path) | **never** — it passes no stream |
| key rotation (`rotate_keys`) | no production caller exists |

The rename gap is recent and ours: `dossier-audit` (2026-09-22) routed renames
to this stream and documented that "a caller from the API always passes one".
There is no API path for a rename. The only real caller is the CLI, and it
passes nothing, so `renamed()` returns silently every time. The `dossiers` spec
currently promises a record that is never written.

## What Changes

1. **The stream moves into PostgreSQL** — a new table,
   `key_lifecycle_events`, beside `audit_records`. CNPG runs three instances with
   failover; it is the one genuinely durable store in this stack, and the
   document chain already lives there. An authorisation trail that is less
   durable than the thing it authorises is backwards.
2. **Append-only at the schema level**, with the same
   `BEFORE UPDATE OR DELETE` trigger that guards `audit_records`.
3. **Hash-chained**, reusing the document chain's mechanism (advisory lock,
   `prev_hash UNIQUE`, `verify_chain`). See `design.md` for why now and not in a
   later change.
4. **Every writer reaches it.** The rename CLI passes the stream. In production
   code a missing stream is an error, not a silent return — the `None` default
   is exactly how the rename gap stayed invisible.
5. **The WORM export reads the table**, serialised canonically in `seq` order,
   instead of copying a file that may not exist.

## Impact

- New table and trigger via `wordsworth-init` (PreSync); no change to
  `audit_records`.
- `WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH` loses its meaning in production. The
  JSONL driver stays as a test double behind the same protocol.
- Nothing to migrate that still exists, except whatever the live file holds at
  rollout. What was lost before stays lost, and is written down as such.
  Revocations are also recorded on the grant row itself (`revoked_at`), so that
  one fact survives independently.

## Not in scope

- **Wiring up key rotation.** `rotate_keys` has no production caller; once it
  gets one, it writes here like everything else. Giving it one is its own change.
- **Scheduling the WORM export.** It has no caller either. Making it read the
  right source comes first.
