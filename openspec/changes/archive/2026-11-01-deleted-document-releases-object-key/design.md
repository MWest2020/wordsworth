# Design

## Release, not a special case

Decided in `originals-cipher-and-key-store` design.md §4: deleting releases
the key; excluding state `deleted` in every existence rule was rejected (each
future rule can forget it), and so was refusing re-ingest of deleted bytes
(it blocks a legitimate re-publication). After the release, `live_document_for`,
`register_live`, the unique index, the OCR owner check and `api.py`'s
already-indexed shortcut all see the key as free, without a line of change.

## The placeholder

`deleted/<document_id>`: unique by construction, so the partial unique index
never refuses it, and it can never equal a content-addressed key
(`documents/<sha256>`). Nothing is stored under it; every reader of an object
already refuses a deleted document (its state), and a stray `store.get` on it
fails loudly as a missing object.

## Order inside the deletion

`delete_document` keeps its order (index, object, then the database work).
It computes the object check from the current key, removes the object if no
other document claims it, and only then, inside the caller's transaction,
writes the placeholder and the `deleted` record with `released_object_key`. A
failure before the commit leaves the row with its real key, so a rerun finds
it as before. The `deleted` record holds ids and counts; the former key is an
id (a hash of bytes the system received), not a value, text, token or
filename.

`_object_claimed_elsewhere` keeps its `!= DELETED` test: documents deleted
before the one-off release still carry their real key until it runs.

## The one-off release

`wordsworth-release-deleted-keys` finds documents in state `deleted` whose
`object_key` does not start with `deleted/`, and with `--apply` releases each
the same way, appending one audit record per document (`step` `release-key`,
from and to `deleted`, payload `released_object_key`). Idempotent: a released
document is not found again. `docs/reference/cli.md` says to run it once after this
change is deployed; until then those documents behave as today.

## Where the code goes

`deletion.py` is 168 lines: the release adds a few. The CLI goes in a new
module `release_deleted.py` with its entry point in `pyproject.toml`.
