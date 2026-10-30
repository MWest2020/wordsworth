# Design

This design settles the five points the architect left open on #306 (verdict
of 2026-10-30 21:24) and the cache question. Each is a decision, with the
reason; none is left to the builder. Points that only the later changes act
on are decided here too, so the four changes agree.

## 1. No unsettled question ships as a task

The "fourth guess-point" that #306 left open was, read from the full verdict
of 2026-10-30 20:57: *no task or spec named the read sites of an original*.
It is settled below (point 2) and owned by `originals-encrypted-ingest`. No
change in this chain tells a builder to stop and report.

## 2. The read side of an original

Every reader of an original goes through `get_original`; there is no second
way. The readers, named so no build can miss one: `pipeline.py:272`
(`process`), `pipeline.py:455` (`reanonymize`, also via `reprocess.py`),
`recovery.py:61` (OCR input), `api.py:736` (redacted PDF), `api.py:1580`
(reveal PDF). They move in `originals-encrypted-ingest`, together with the
ingest write, because the value of that change is that no path reads an
original outside the driver.

What this change adds so that a missed reader cannot fail silently: the plain
`ObjectStore.get` refuses an object whose first bytes are the sealed magic,
raising `SealedObjectError`. Rejected: returning ciphertext and trusting every
caller to know; that is the silent fallback CLAUDE.md forbids. Cost: one
prefix comparison per `get`.

## 3. What the ciphertext is bound to

- The associated data (AAD) is `b"wordsworth-original/1" || object_key.encode()
  || key_id`. It does **not** contain a document id. Reason: an object is
  content-addressed and can legitimately belong to more than one document over
  its life (a superseded copy shares it with its survivor; after a deletion the
  same bytes can be ingested again as a new document). Binding the ciphertext
  to a document id would force a re-seal over an existing object at every
  change of owner, and a re-seal over an existing object is exactly the crash
  window in which a live document ends up pointing at bytes it cannot open.
  Binding to the object key still makes a sealed object fail to open when it is
  copied or swapped to another key; binding the `key_id` makes a header whose
  key id was changed fail too. Rejected: AAD over the plaintext hash, because
  `open` would need the plaintext before decrypting it; AAD over the document
  id, for the reason above.
- `document_keys.document_id` records which document the key belongs to (the
  document that currently owns the object), for crypto-shred. Changing it is a
  plain row update with no cryptographic effect, so a rollback of it is
  harmless.
- Ingest registers the document (and gets its id) before it writes the object,
  because the key row needs the id; that reordering is a task with its own
  test in `originals-encrypted-ingest`.

## 3a. `put_original`: one idempotent rule for every writer

`put_original(document_id, object_key, data)` is the only way an original is
written, by ingest (`originals-encrypted-ingest`), OCR recovery
(`originals-ocr-sealed`) and the corpus migration (`originals-encrypt-existing`).
It never mints a second key for an object, and never overwrites bytes that a
document can still read:

1. Key row for `object_key` exists, and the stored object carries the sealed
   header with that row's `key_id`: **no write** (re-ingest does not re-seal).
   If the row's `document_id` differs, it is updated to `document_id`. Callers
   guarantee `document_id` is the live owner of `object_key` (ingest through
   `register_live`, OCR recovery through its owner check), so this moves a key
   from a deleted or retired document to the one that now holds the bytes.
2. Key row exists, but the object is missing or its header names another
   `key_id` (an object left by a rolled-back write): seal with **the row's
   data key** and write. Nothing readable is overwritten: such an object opens
   under no row.
3. No key row, and the object is missing or sealed (an orphan from a
   rolled-back write): mint a key, insert the row (in a savepoint, adopting the
   winner on a primary-key conflict, as `register_live` does), then write.
4. No key row, and the object is a legacy plaintext object: **no write**,
   return "legacy". Replacing it is `originals-encrypt-existing`, which verifies
   before it removes plaintext; doing it here would put the only readable copy
   of a live document inside an uncommitted transaction.

A key service that is unreachable or refuses raises `OriginalsKeyUnavailable`
at any step, before anything is written. `put_original` returns whether it
wrote, so a caller whose transaction then fails deletes the object it wrote:
by rules 2 and 3 that object was readable by nobody before the call.
Crash between the row and the object (the row is in the caller's transaction,
the object write is not):

- crash before the object write: the transaction rolls back, nothing remains;
- crash after the object write, before the commit: a sealed object without a
  key row (rule 3 case) or with a row that does not open it (rule 2 case).
  Neither is pointed at by a committed new document, neither holds plaintext,
  the next write of the same bytes repairs it, and `wordsworth-sealed-orphans`
  removes both kinds.

## 4. A deleted document does not hold its object key

Today a deleted document keeps its `object_key` with `superseded_by` NULL, so
`uq_documents_live_object_key` still counts it as the live document: a
re-ingest of the same bytes adopts the deleted row, whose object is gone.
Decided: deleting a document **releases its object key**: the row's
`object_key` becomes `deleted/<document_id>`, and the real key is recorded in
the deletion audit record (a content hash, no personal data). Every existence
rule (`live_document_for`, `register_live`, the OCR owner check, `api.py:1072`)
then needs no special case. Rejected: excluding state DELETED in every rule
(each future rule can forget it), and refusing re-ingest of deleted bytes
(blocks a legitimate re-publication). This is its own small change,
`deleted-document-releases-object-key`, with a one-off release for documents
deleted before it.

## 5. One key row per object, not per document

An OCR-recovered document has two objects: the scan (kept, per the ocr spec)
and the OCR'd PDF. So `document_keys` is keyed by `object_key` (primary key),
with `document_id` indexed. Crypto-shred deletes every row of a document.
Columns: `object_key`, `document_id`, `key_id`, `kek_ref`, `wrapped_material`,
`created_at`, `sealed_at`.

`sealed_at` says the object under this key is sealed. `put_original` sets it
in the same insert (its write follows in the same call, and a failure rolls
the row back). `originals-encrypt-existing` inserts the row with `sealed_at`
NULL and commits it **before** it replaces a plaintext object, and sets it only
after the sealed object verified: a crash in between then leaves a row that
does not yet claim a sealed object, so the plaintext still reads and the run
resumes. The downgrade guard (an object with a key row but no header is
refused) applies to rows with `sealed_at` set.

## 6. The cache: one rule

The unwrap cache is a bounded LRU **and** each entry expires after
`settings.key_cache_ttl`. Size bound: `WORDSWORTH_DOCUMENT_KEY_CACHE_SIZE`,
default 1024. Why both: the size keeps memory flat however large the corpus
(one key per document); the TTL is the existing promise that a revoked or
rotated KEK takes effect within `key_cache_ttl` seconds, which is the whole
point of an organisation holding its own key. `DurableKeyProvider._cache`
(pseudonymisation keys) is not touched: it is keyed per domain and type.

## Format

`WWENC` (5 bytes), version `0x01` (1 byte), `key_id` (12 bytes ASCII, the
12-hex-character ids `keys._mint()` already produces), nonce (12 bytes), then
the GCM ciphertext with its 16-byte tag. Rejected: a 16-byte binary key id,
which would not match the ids `key_vault` uses.

## KEK per domain

`WORDSWORTH_ORIGINALS_KEK` (default: the current `transit_kek_name`) and an
optional `WORDSWORTH_ORIGINALS_KEK_BY_DOMAIN` (JSON object, domain → KEK name).
The KEK used is the one for the document's domain at seal time, recorded as
`kek_ref` in the row; `open` unwraps with the row's `kek_ref`, never with the
current setting. A changed setting therefore affects new objects only.

## Orphans

S3 and Postgres cannot share one transaction. A sealed object written while
the database transaction then rolled back opens under no key row: either it has
no row, or the row for its key names another `key_id` (§3a, rule 2). It is
unreadable by construction (no plaintext risk), the next write of the same
bytes repairs it, and `wordsworth-sealed-orphans` removes it: a sealed object
under `documents/`
that opens under no key row (no row for its key, or a row with another
`key_id`), older than one hour so a write in flight is never touched; dry-run
unless `--apply`. A writer that fails inside its own code after
`put_original` wrote deletes the object itself; a failed commit in a caller is
left to the sweep.

## Availability

Wrong, missing or unreachable KEK: `open` raises `OriginalsKeyUnavailable`;
there is never a fallback to plaintext for an object that has a key row.
Whether ingest may stop when OpenBao is down, in irreversible mode too, is
Mark's call (#318); the working default is yes, fail closed.
