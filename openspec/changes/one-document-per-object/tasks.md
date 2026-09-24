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
- [ ] 2.1 Dry run in the cluster; the counts match 173 / 159 / 173.
- [ ] 2.2 Apply. Afterwards: 618 live documents, 611 distinct `object_key`s
      in the index and no key twice, and every dossier count down by its
      copies.

## 3. Release 2 — the constraint
- [ ] 3.1 Unique index on `object_key` where `superseded_by IS NULL`.
- [ ] 3.2 Registration adopts the existing document on a unique violation.
      Test: two concurrent registrations of the same bytes give one document.
- [ ] 3.3 OCR recovery that collides supersedes itself (Decision 7). Test.
- [ ] 3.4 Deploy; the init creates the index; the constraint is visible in
      `pg_indexes`.
