# Design: key-audit-in-postgres

## Decision 1 — PostgreSQL, not a durable volume

**Chosen:** a table in the existing database.

**Rejected: mount a PersistentVolume at the JSONL path.** It is one line of
manifest and it fixes the restart. But the only storage class in the cluster is
`local-path`, so the audit trail would be pinned to one node — the exact
fragility `hoge-beschikbaarheid` exists to remove. And a second writer in
another pod (the ingest Job, a CLI Job) would need the same volume, which
`ReadWriteOnce` does not allow. Postgres already solves both: replicated,
reachable from every pod, and already holding the document chain.

**Rejected: log shipping (stdout → a log collector).** Durable, but not
queryable as a trail, not append-only by construction, and it adds a component
the trail would then depend on.

## Decision 2 — a table of its own, not `audit_records`

`audit_records.document_id` is a NOT NULL foreign key, and
`key-lifecycle/spec.md` requires that it stay one — no sentinel "system
document". These events have no document by definition; that is why the stream
was separate in the first place. Nothing about that reasoning changes by
moving to Postgres.

## Decision 3 — chain it now

`key_audit_export.py` says it plainly: the stream is append-only but *not*
chained, so a host compromised before an export could rewrite it, and the
export would faithfully preserve the rewrite. It names chaining as a separate
change (`harden-key-audit-chain`) that was never proposed.

Doing it here costs two columns and a lock that already exists
(`audit.append` has the pattern, `verify_chain` has the check). Doing it later
costs a migration over rows that were written unchained. The table is new and
starts empty; that makes this the cheapest moment the chain will ever have.

Its own chain, not the document chain: a separate advisory-lock key, its own
genesis. Interleaving the two would couple document throughput to authorisation
writes for no benefit.

## Decision 4 — no silent `None` in production

`dossiers.rename(..., lifecycle=None)` and `dossier_events.renamed()` return
quietly when no stream is passed. The docstring defended that as "the test
mode … a caller from the API always passes one". No API caller exists; the one
real caller passes nothing. The default did not make the code safer, it made a
missing record look like a design choice.

So: production entry points (API, console, CLIs) get the stream from one
factory, and a writer that receives none raises. Tests inject a double
explicitly — which they already do.

## Decision 5 — the export serialises rows

`key_audit_export.py` exports *bytes*, deliberately: "an export that
re-serialises would produce a file that means the same and is different". That
argument holds when a file is the source of truth. Once the table is, the
canonical form is the rows in `seq` order serialised one way, and that is what
`audit_export.export_jsonl` already does for the document chain. Same function
shape, so there is one definition of what an export looks like.

## What is lost, said once

Everything written to the stream before this change lands and before the
rollout restarts the pod. There is no copy. The grant rows carry `revoked_at`,
the roles table carries current state, and the dossier rows carry current
names — so the current *state* is intact. The *history* of how it got there is
not, and no migration can bring it back.
