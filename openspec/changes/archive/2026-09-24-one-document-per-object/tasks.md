# Tasks: one-document-per-object

Two releases; the order is forced by the constraint (design, Decision 6).

## 1. Release 1 — the state and the cleanup
- [x] 1.1 `State.SUPERSEDED`, terminal, reachable from every state; the
      comment in `states.py` names it as the one edge out of a terminal state.
- [x] 1.2 `documents.superseded_by` (nullable FK to `documents.id`) and a
      trigger that refuses changing it once set. Test: an UPDATE of a set
      pointer raises.
- [x] 1.3 `supersede(session, copy, survivor, actor)`: the audit record, the
      pointer, the dossier removals and the index deletion, in one transaction
      where the database allows and in a stated order where the index does not.
- [x] 1.4 `SearchIndex.delete(doc_id)` in the protocol, the in-memory index
      and OpenSearch.
- [x] 1.5 Walk every reader that counts, lists, searches or reveals by
      document, and list here what each does with a superseded one. Not
      assumed: listed.

      Walked 2026-09-24. Leaving the index covers every reader that goes
      through it (search, hybrid, ask, topics, summaries); leaving the
      dossiers covers every scope. The rest:

      | Reader | With a superseded document | Change |
      |---|---|---|
      | `GET /documents/{id}/state` | `superseded` + `superseded_by` | added the pointer |
      | `POST /documents/{id}/reveal` | 409, names the survivor | **guard added** |
      | Ingest skip (`api.py`), `pipeline.ingest`, dataset run | looked up the *first* row with the key, which can be a copy | **now `live_document_for`** |
      | Console front page + total | copies are the most recently touched, would fill the page | **filtered to live** |
      | `dossiers.add` | would put a copy back in a case | **refused** |
      | `backfill_dossier.orphans` | copies belong nowhere, would be reported and re-added | **filtered to live** |
      | `wordsworth-dossier-uit-herkomst` | would assign copies by provenance | **filtered to live** |
      | Export, reprocess, OCR recovery | select by state (`indexed`, `unprocessable_ocr`) | none: `superseded` drops out |
      | Metrics, report | group by whatever state exists | none: `superseded` shows as its own count |
      | Console document page | shows the state | none |
      | `backfill_filenames` | may name a copy | none: harmless |

      Every guard marked in bold was checked once with its fix removed; each
      made a test fail. Two ingest-lookup tests passed with the fix removed
      at first: superseding UPDATEs the copy, which moves it to the end of the
      heap, so an unordered lookup found the survivor by luck. They now touch
      the survivor last, forcing the unlucky order.
- [x] 1.6 `GET /documents/{id}` answers `superseded` + `superseded_by`;
      reveal on a superseded document is refused and names the survivor.
- [x] 1.7 `wordsworth-dedupe`: dry run by default; `--apply` retires every
      copy in favour of the oldest registered one. It stops if its counts
      differ from what it is told to expect.

      Deviation from the design, stated: index entries can only be counted by
      removing them, so `--expect-index-entries` is checked after the run
      (exit 1 on a difference), not before. Copies and memberships are
      checked before anything changes.

## 2. Run it
- [x] 2.1 Dry run in the cluster; the counts match 173 / 159 / 173.
- [x] 2.2 Apply. Afterwards: 618 live documents, 611 distinct `object_key`s
      in the index and no key twice, and every dossier count down by its
      copies.

      Done 2026-09-24 on image `32179060…` (main `eb86cd0`), after
      `wordsworth-reprocess-hosts` had finished, so no job could re-index a
      copy mid-run. The first attempt did not start: `import
      wordsworth.pipeline` had failed in every fresh process since #148
      (fixed in #164, which also found `wordsworth-ingest` broken since
      2026-09-22).

      Dry run: 93 objects, 173 copies, 173 memberships, as measured. Index
      before: 770 entries, 159 extra. `--apply`, batch `dedupe-da5f8130`:
      173 superseded, 0 memberships passed on, 173 removed, 159 index
      entries removed; exit 0.

      Checked independently afterwards: index 611 entries over 611 objects,
      none twice; database 791 documents, 618 live over 618 distinct keys,
      173 `supersede` and 173 `dossier_removed` (actor `dedupe`) records, no
      membership on a superseded document, no survivor itself superseded;
      the document audit chain verifies; a copy answers `superseded` with
      its survivor through the live API. A rerun finds nothing to do.

## 3. Release 2 — the constraint
- [x] 3.1 Unique index on `object_key` where `superseded_by IS NULL`.
- [x] 3.2 Registration adopts the existing document on a unique violation.
      Test: two concurrent registrations of the same bytes give one document.
- [x] 3.3 OCR recovery that collides supersedes itself (Decision 7). Test.

      Built 2026-09-24. The index lives in the model (new databases) and in
      `init_schema` (existing ones); creating it over remaining copies fails
      the init on purpose. `register_live` is the one way in for new bytes:
      ingest, the dataset run. OCR recovery checks the owner of the OCR'd
      object first and supersedes itself `as_object`; the api ingest path then
      updates the owner's dossiers in the index instead of processing a
      retired document. Tests in `tests/test_one_live_document.py`, each guard
      checked once with its fix removed. Release-1 tests that need live copies
      now ask for a pre-constraint database (`legacy_copies`), and two test
      fixtures that reused one placeholder key for different documents got
      their own keys.

      Not tested: the same collision branch in `ingest_corpus`, which builds
      OpenSearch and S3 from config inside the function and cannot be given
      fakes. It mirrors the api branch line for line.
- [x] 3.4 Deploy; the init creates the index; the constraint is visible in
      `pg_indexes`.

      Deployed 2026-09-24 on image `409b931b…` (main `e674005`, homelab
      `0ee60b0`). `pg_indexes`: `CREATE UNIQUE INDEX
      uq_documents_live_object_key ON public.documents USING btree
      (object_key) WHERE (superseded_by IS NULL)`. Smoke from the cold side:
      inserting a second live document for an existing object, inside a
      transaction that was rolled back, was refused with `duplicate key value
      violates unique constraint "uq_documents_live_object_key"`; the table
      still held 791 rows.
