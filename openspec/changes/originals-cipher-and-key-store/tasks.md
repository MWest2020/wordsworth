# Tasks

No ingest, read-site or OCR change in this build. A skipped test counts as
failed for every reviewer.

## 1. Envelope format
- [ ] 1.1 `src/wordsworth/originals_envelope.py`: header (`WWENC`, version,
      12-byte `key_id`, nonce), `seal(dek, key_id, object_key, plaintext)` and
      `open(...)`, AAD as design.md §3 (object key and key id, no document
      id). Proved by: a round-trip
      test (bytes equal) and a test that the sealed bytes start with the header
      and contain no marker string from the plaintext.
- [ ] 1.2 Tampering fails closed: a flipped ciphertext byte, a flipped tag
      byte, a changed header `key_id`, and sealed bytes copied to another
      `object_key` (and two sealed objects swapped) each raise and return no
      plaintext. Proved by: five negative tests.

## 2. Key store
- [ ] 2.1 `document_keys` table (columns and primary key per design.md §5) and
      `DocumentKeys(transit_for, …)` in `src/wordsworth/document_keys.py`
      (not in `models.py`, which is past the 200-line invariant):
      - `mint(session, document_id, object_key, domain)` creates a 32-byte
        DEK, wraps it with `transit_for(kek_name_for(domain))`, stores the
        wrapped blob and `kek_ref` = that name, and inserts the row in a
        savepoint that adopts the winner on a primary-key conflict, as
        `register_live` does;
      - `unwrap(session, object_key)` uses `transit_for(row.kek_ref)`
        (design.md "KEK per domain").

      `OriginalsKeyUnavailable` and `kek_name_for` are defined in the same
      module (design.md "Files and known drift"); `SealedObjectError` stays in
      `object_store.py`. If the module passes 200 lines, lift the unwrap cache
      onto `cache.LruCache` and keep the model reachable from `db.py`'s import.
      Proved by: `wc -l` at most 200 for `document_keys.py` (checked in
      review), a test that `from wordsworth.document_keys import
      OriginalsKeyUnavailable, kek_name_for` works and that `object_store.py`
      does not import `originals_envelope` (grep in review), a round-trip test against the name-keyed `FakeTransit`
      factory, a test that the row never holds the clear DEK, and three
      negative tests: a tampered `wrapped_material`, a row whose `kek_ref`
      names another KEK than the one that wrapped it, and a Transit that
      raises. Each fails with `OriginalsKeyUnavailable` and no key material.
- [ ] 2.4 `db.py` imports `document_keys`, so `Base.metadata` carries the
      table (design.md "Files and known drift"). Proved by: a test that runs
      `init_schema` in a subprocess that never imports `document_keys` itself
      and finds `document_keys` with its index.
- [ ] 2.2 The unwrap cache follows design.md §6: bounded size and TTL. Proved
      by: a test that unwraps more objects than the size and asserts the cache
      stays at the size and an evicted key is unwrapped again via Transit; and
      a test with a fake clock that an entry older than `key_cache_ttl` is
      unwrapped again.
- [ ] 2.3 KEK per domain (design.md "KEK per domain"): the row records the KEK
      used; `unwrap` uses the row's `kek_ref` even after the setting changes.
      Proved by: a config test and a test that changes the setting between
      seal and open, with the name-keyed `FakeTransit` factory, so the old
      name is needed to open.

## 3. OriginalsStore and the guards
- [ ] 3.0 `OriginalsStore` and `PutResult` live in
      `src/wordsworth/originals_store.py`; `originals_envelope.py` holds only
      `seal`, `open` and the header (design.md "Files and known drift").
      Proved by: a test that `from wordsworth.originals_store import
      OriginalsStore` works, and `wc -l` showing both modules at most 200 lines
      (checked in review).
- [ ] 3.1 `OriginalsStore(objects, keys)` holds no session (design.md §3a
      "Sessions").
      - `put_original(session, document_id, object_key, data)` follows the
        five rules of design.md §3a, inspects the stored object through
        `objects.get_raw`, and returns a `PutResult` (`WROTE`, `UNCHANGED`,
        `LEGACY`; design.md §3a), never a bool or a string.
      - `get_original(session, object_key)` reads the row, `get_raw`s the
        object and opens it.
      - The underlying store is exposed as `.objects`.

      Proved by:
      - one test per rule:
        - 1: existing row and matching object: no write, `UNCHANGED`, row
          moved to the new document id;
        - 2: row and missing object: sealed with the row's key, opens,
          `WROTE`;
        - 2: row and an object with another `key_id`: rewritten, opens,
          `WROTE`;
        - 3: no row and an orphan: new row, opens, `WROTE`;
        - 4: legacy object with no row: untouched, `LEGACY`;
        - 4: legacy object with a row whose `sealed_at` is NULL: untouched,
          `LEGACY`;
        - 5: header-less object with a row whose `sealed_at` is set: raises
          `SealedObjectError`, nothing written;
      - a test that `bool()` of each `PutResult` member raises `TypeError`,
        so `if wrote:` cannot compile into a wrong delete;
      - a round trip;
      - a test that two concurrent first writes of one object end with one
        row and an object that opens.
- [ ] 3.2 Crash between key row and object write leaves no unreadable or
      orphaned data: with a store that raises on `put`, the caller's rollback
      leaves no row and no object; with a session that fails after
      `put_original` wrote, deleting the written object (the caller contract)
      leaves no row and no object, and a following `put_original` of the
      same bytes in a fresh transaction yields an object that opens. With an
      unreachable key service nothing is written. The caller contract is delete
      only on `wrote is PutResult.WROTE`, proved both ways with a caller
      written as `ingest` will be: a legacy object plus a failed caller commit
      leaves the legacy object intact (`LEGACY`, no delete), and a `WROTE`
      result plus a failed commit removes the written object. Proved by: five
      tests.
- [ ] 3.3 `ObjectStore.get_raw(key)` and `ObjectStore.iter_objects(prefix)`
      are added to the `ObjectStore` protocol and to both drivers (S3 and
      in-memory) in the same commit, so the `isinstance` check at
      `tests/test_object_store.py:33` covers both; the ad-hoc fake at
      `tests/test_dossiers.py:21` needs no change. Plain
      `get` is `get_raw` plus the sealed-magic guard and refuses a sealed
      object with `SealedObjectError` (design.md §2). Proved by: a test on the
      S3 driver's `get` path with a sealed object, one that a header-less
      object is still returned as before, and one that `get_raw` returns the
      sealed bytes unchanged on both drivers, and the existing `isinstance`
      test passing against the extended protocol. The `object-storage` delta
      is proved by two tests: unsealed bytes put and fetched are identical, and
      a sealed object fetched through plain `get` raises `SealedObjectError`
      and returns no bytes, on both drivers.
- [ ] 3.4 Downgrade refused: `get_original` on an object whose key row has
      `sealed_at` set but which carries no header raises; a legacy object (no
      key row, no header) and an object whose row has `sealed_at` NULL are
      returned as they are. Proved by: a negative test and two tests.

## 4. Orphans
- [ ] 4.1 `wordsworth-sealed-orphans [--apply]` (new module
      `sealed_orphans.py`, entry point in `pyproject.toml`; uses
      `iter_objects(prefix)` from task 3.3, yielding key and last-modified;
      reads headers through `get_raw`): lists sealed
      objects under `documents/` that open under no key row (no row, or a row with another
      `key_id`) and are older than one hour; deletes only with `--apply`.
      Proved by: tests with an orphan without a row and one with a mismatched
      row (listed, removed on apply), a sealed object with its row
      (untouched), a young orphan (untouched), a legacy object (untouched).

Task 4.1 is the only slice that may split off into a follow-up change. If it
does, that change is named in the PR and in this file, and keeps its tests and
its how-to; the task is never dropped (design.md §3a depends on the sweep).

## 5. Logs
- [ ] 5.1 Clear DEK bytes never reach logs or exception messages. Proved by: a
      test that captures logs during seal, open and every failure above and
      asserts the DEK (raw, hex and base64) is absent.

## 6. Docs
- [ ] 6.1 `docs/reference/architecture.md` (storage section): the sealed format,
      `document_keys`, the plain-`get` guard, and that nothing is sealed yet
      until `originals-encrypted-ingest`. ADR-0008 linked. A short how-to
      section for `wordsworth-sealed-orphans` (in `docs/how-to/` where the
      other CLIs are described). `docs/reference/cli.md` lists the new
      `wordsworth-sealed-orphans` entry point and its `--apply` flag. The
      three new settings of design.md "Files and known drift" are described in
      the reference docs next to the other settings. Proved by:
      the docs gate and grep in review for `sealed-orphans` in
      `docs/reference/cli.md` and `docs/how-to/`.

## 7. Sibling changes
- [ ] 7.1 `originals-encrypted-ingest` and `originals-ocr-sealed` code
      `wrote = put_original(...)` with `if wrote is PutResult.WROTE: delete`,
      never `if wrote:`. Proved by: `grep -rn "if wrote"
      openspec/changes/originals-*` finds nothing, and each of the two has the
      legacy-plus-failed-commit test of task 3.2 for its own caller.
