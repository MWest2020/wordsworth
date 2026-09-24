# Tasks: one-document-per-object

Two releases; the order is forced by the constraint (design, Decision 6).

## 1. Release 1 — the state and the cleanup
- [ ] 1.1 `State.SUPERSEDED`, terminal, reachable from every state; the
      comment in `states.py` names it as the one edge out of a terminal state.
- [ ] 1.2 `documents.superseded_by` (nullable FK to `documents.id`) and a
      trigger that refuses changing it once set. Test: an UPDATE of a set
      pointer raises.
- [ ] 1.3 `supersede(session, copy, survivor, actor)`: the audit record, the
      pointer, the dossier removals and the index deletion, in one transaction
      where the database allows and in a stated order where the index does not.
- [ ] 1.4 `SearchIndex.delete(doc_id)` in the protocol, the in-memory index
      and OpenSearch.
- [ ] 1.5 Walk every reader that counts, lists, searches or reveals by
      document, and list here what each does with a superseded one. Not
      assumed: listed.
- [ ] 1.6 `GET /documents/{id}` answers `superseded` + `superseded_by`;
      reveal on a superseded document is refused and names the survivor.
- [ ] 1.7 `wordsworth-dedupe`: dry run by default; `--apply` retires every
      copy in favour of the oldest registered one. It stops if its counts
      differ from what it is told to expect.

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
