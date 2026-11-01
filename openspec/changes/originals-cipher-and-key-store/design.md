# Design

This design settles the five points the architect left open on #306 (verdict
of 2026-10-30 21:24) and the cache question. The amendment of 2026-10-31
settles the four seam questions of the architect's verdict on #320 (31 Oct
00:28): the raw read (§2), the KEK factory ("KEK per domain"), transaction
ownership (§3a, "Sessions") and the header-less object with a key row (§3a,
rules 4 and 5). Each is a decision, with the
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

**The raw read.** The `ObjectStore` protocol gets one unguarded read,
`get_raw(key) -> bytes`, in both drivers. `get` is `get_raw` plus the
magic-prefix guard. Exactly three callers use `get_raw`, and each needs the
sealed bytes or the header:
- `OriginalsStore.get_original`;
- `put_original`'s header inspection (§3a);
- `wordsworth-sealed-orphans`.

Everything else keeps `get`. `SealedObjectError` and the magic-prefix
predicate live in `object_store.py`, the lower layer, so `object_store` never
imports `originals_envelope`.

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

`put_original(session, document_id, object_key, data)` is the only way an original is
written, by ingest (`originals-encrypted-ingest`), OCR recovery
(`originals-ocr-sealed`) and the corpus migration (`originals-encrypt-existing`).
It never mints a second key for an object, and never overwrites bytes that a
document can still read:

1. Key row for `object_key` exists, and the stored object carries the sealed
   header with that row's `key_id`: **no write**, return `PutResult.UNCHANGED` (re-ingest does not re-seal).
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
4. The stored object is a legacy plaintext object (no sealed header), and
   there is **no key row, or a key row with `sealed_at` NULL**: **no write**,
   return `PutResult.LEGACY`. The second case is the state `originals-encrypt-existing`
   commits on purpose before it replaces a plaintext object. Replacing it is
   `originals-encrypt-existing`, which verifies before it removes plaintext;
   doing it here would put the only readable copy of a live document inside an
   uncommitted transaction.
5. The stored object has no sealed header, but its key row has `sealed_at`
   set: a downgrade (the sealed object was replaced by plaintext). **Raise
   `SealedObjectError`; no write.** Overwriting it would repair by guess;
   loud beats quiet. This is the same state `get_original` refuses (task 3.4).

Rule 2 writes regardless of `sealed_at`, and sets `sealed_at` when it writes.
Rules 2 and 3 return `PutResult.WROTE`.

**The result is an enum, not a bool.** `PutResult` has three members: `WROTE`,
`UNCHANGED`, `LEGACY`. A bool cannot tell "legacy, left alone" from "wrote",
and a `"legacy"` string is truthy, so `if wrote: delete(key)` would delete a
live legacy object after a failed commit: the only readable copy of a
document. Decided: callers delete only on `wrote is PutResult.WROTE`, and
`PutResult.__bool__` raises `TypeError`, so `if wrote:` fails the first time
it runs instead of being a quiet wrong delete. Rejected: a bool (loses the
legacy case), a `"legacy"` string (truthy), a tuple (callers unpack and can
still test the wrong element). The sibling changes `originals-encrypted-ingest`
and `originals-ocr-sealed` code `wrote is PutResult.WROTE` in their design and
tasks.

**Sessions.** The session is a per-call parameter:
- `put_original(session, document_id, object_key, data)`;
- `get_original(session, object_key)`;
- `DocumentKeys.mint(session, …)`;
- `DocumentKeys.unwrap(session, object_key)`.

That is the pattern of `register`, `ingest` and `transition` in `pipeline.py`.
The key row therefore lands in the caller's transaction (the crash analysis
below depends on it). An `OriginalsStore(objects, keys)` holds **no
session**, so one process-lifetime instance (built once in `serve.py` by
`originals-encrypted-ingest`) keeps the unwrap cache of §6 warm across
requests.

A key service that is unreachable or refuses raises `OriginalsKeyUnavailable`
at any step, before anything is written. `put_original` returns a `PutResult`, so a caller whose transaction then fails
deletes the object only when the result `is PutResult.WROTE`: by rules 2 and 3
that object was readable by nobody before the call. On `LEGACY` and
`UNCHANGED` the object was readable before and the caller never deletes it.
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
The KEK used is the one for the document's domain at seal time. The domain
comes from `pipeline.document_domain(session, document_id)`, imported inside
the function (`pipeline` imports this module from the next change on, and a
module-level import would then cycle). The KEK name is recorded as `kek_ref`
in the row. `open` unwraps with the row's `kek_ref`, never with the current
setting, so a changed setting affects new objects only.

**The seam is a factory, not one Transit.** `OpenBaoTransit` binds its KEK
name at construction, because OpenBao's encrypt and decrypt endpoints carry it
in the path. So `DocumentKeys` takes `transit_for: Callable[[str], Transit]`:
- `mint` wraps with `transit_for(kek_name_for(domain))`;
- `unwrap` uses `transit_for(row.kek_ref)`.

In production the factory returns one `OpenBaoTransit(url, token, name)` per
name, cached. In tests it is keyed by name:
`lambda name: FakeTransit(kek=sha256(name.encode()).digest())`. A key wrapped
under one name then really fails to unwrap under another, and the wrong-KEK
test of task 2.1 has something to vary. `FakeTransit` itself does not change.

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

## Files and known drift

- `config.py` (442 lines) and `models.py` (401) are already past the
  files-≤-200 invariant. This change adds three settings to `config.py`
  (`WORDSWORTH_ORIGINALS_KEK`, `WORDSWORTH_ORIGINALS_KEK_BY_DOMAIN`,
  `WORDSWORTH_DOCUMENT_KEY_CACHE_SIZE`) as earlier changes did. That is the
  precedent, not fresh drift, and the PR says so. Split `config.py` in its own
  change, not here.
- `object_store.py` is 107 lines; `get_raw`, the guard and `iter_objects`
  belong there. `get_raw` and `iter_objects` are added to the `ObjectStore`
  protocol and to both drivers (S3 and in-memory) in the same commit. The
  protocol check at `tests/test_object_store.py:33` (`isinstance(
  InMemoryObjectStore(), ObjectStore)`) then covers both. The ad-hoc fake at
  `tests/test_dossiers.py:21` only needs `put()` and needs no change.
- **The split.** The 200-line limit decides it. `originals_envelope.py` holds
  `seal`, `open` and the header. `originals_store.py` holds `OriginalsStore`,
  `PutResult` and the `put_original` rules of §3a; it imports
  `originals_envelope`, never the reverse. The class name `OriginalsStore` is
  the public import. Rejected: one module for both, which would not stay under
  200 lines.
- **Placement of the errors and the name function.** `OriginalsKeyUnavailable`
  and `kek_name_for` live in `document_keys.py`, next to the model, `mint`,
  `unwrap` and the cache. `SealedObjectError` stays in `object_store.py`, so
  the lower layer never imports `originals_envelope`. If `document_keys.py`
  goes over 200 lines, the cache is lifted out onto `cache.LruCache` (adding
  the TTL there or in a thin wrapper), and the model stays importable from
  `db.py`'s import.
- **One build.** This stays one change and one build. Only task 4.1 (the sweep
  and its how-to) may split off, and then as a named follow-up change, never a
  dropped task: the crash analysis in §3a relies on the sweep.
- **Plain `get` narrows an existing promise.** The `object-storage` scenario
  "bytes put and fetched are identical" holds for unsealed objects only, since
  plain `get` now raises on a sealed object (§2). The delta spec
  `object-storage` says so and adds the loud-failure scenario.
- The `document_keys` model lives in `document_keys.py`, outside `models.py`.
  A model class in a module nobody imports is absent from `Base.metadata`, so
  `init_schema`/`wordsworth-init` would create every table except this one
  while the tests stayed green. Guard: `db.py` imports `document_keys` next to
  `from .models import Base`. Proof: a test runs `init_schema` in a fresh
  interpreter (subprocess) that never imports `document_keys` itself, and
  finds the table.
- `OriginalsStore` is a concrete class, not a protocol with drivers. It
  composes two existing seams (`ObjectStore`, `Transit`) and adapts no
  external system, so the driver pattern doesn't apply. The architecture doc
  says so.

## Availability

Wrong, missing or unreachable KEK: `open` raises `OriginalsKeyUnavailable`;
there is never a fallback to plaintext for an object that has a key row.
Ingest stops when OpenBao is down, in irreversible mode too: fail closed
(#318, decided 2026-10-31).
