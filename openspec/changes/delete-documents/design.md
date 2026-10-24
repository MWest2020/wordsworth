# Design

## The row stays; the content goes

`audit_records.document_id` is a non-null foreign key to `documents.id`, and the
audit table has no UPDATE or DELETE. Removing the `documents` row would either
break the trail or require deleting audit records, which is the one thing this
system never does. So deletion removes everything *about the content* (object,
text, pseudonyms, mappings, index entries, grants) and leaves the `documents`
row and its audit records. This is the same reason a superseded copy keeps its
row.

## `deleted` is a state, derived like every other

`documents.current_state` is derived from the latest audit record (CLAUDE.md).
The `deleted` audit record therefore makes `deleted` the document's state, and
the state machine gains it: terminal, reachable from every state, like
`superseded`. A second state column or a flag on the row would be a mutable
status next to the trail. The transition and its audit record are written in
one transaction, as everywhere else.

## The audit record carries ids and counts, never values

The record holds the document id, who deleted it, and how many of each thing
were removed (object, text rows, pseudonyms, mappings, index entries, grants).
It holds no filename, no text, no token and no value: a deletion record that
repeated what was deleted would keep it.

## Order and failure

The content is removed before the `deleted` record is committed, and any removal
that fails is a hard error: the record is not written, the document stays in its
previous state, and the call reports which part failed. A `deleted` record over
content that is still there would say something false; this is the null-vector
rule applied to deletion, no silent fallback. A rerun after a failure finishes
the work, because removing what is already gone is a no-op.

## Authorisation

Only role `beheerder` or an issuer label may delete, checked before anything is
read or removed. A refusal changes nothing and writes no `deleted` record. The
beheerder gets no path around `authorize()`-style checks that other callers do
not have; this follows the rule in the `rollen` capability. How a caller is
shown to hold the role is an open question in the proposal.

## `--dry-run`

The CLI reports the counts it would remove, using the same code that deletes,
and stops before the first removal. It writes no audit record, because nothing
happened. The API has no dry run; the CLI is where a human looks first.

## Rejected alternatives

- **Delete the `documents` row and its audit records.** Breaks the append-only
  guarantee and the hash chain.
- **Soft-delete flag on `documents`.** A mutable status column beside the trail,
  and the content would still be there.
- **Reuse `superseded`.** It means "another document replaces this one", keeps
  the text and the index entry, and names a survivor. Deletion has none of that.
- **Best-effort deletion** (log and continue when the index is down). A silent
  fallback; the personal data would still be searchable.
