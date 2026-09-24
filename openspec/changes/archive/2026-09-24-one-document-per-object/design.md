# Design: one-document-per-object

## Decision 1 — retire, never delete

`audit_records.document_id` is a NOT-NULL foreign key and the table refuses
UPDATE and DELETE. A document that has a history cannot be removed without
removing that history, and the history is the point. So a copy stays a row,
keeps every audit record, and gains one more: that it was superseded, and by
which document.

## Decision 2 — `superseded` is a state, and the one edge out of a terminal state

`INDEXED` and `FAILED` are terminal: "terminal states have no outgoing edge"
(`states.py`). A copy is usually `indexed`, so retiring it needs an edge out.

A step without a state change was the alternative: record "superseded" while
the state stays `indexed`. Rejected, because everything that counts or lists by
state (metrics, the console, dossier counts) would keep counting the copy as a
live, searchable document. The state is what readers ask, so the state has to
say it.

So `superseded` is a new terminal state, reachable from **every** state,
including the terminal ones. It is the only edge that leaves a terminal state,
and `states.py` and the lifecycle spec say so, instead of quietly bending the
rule.

## Decision 3 — `documents.superseded_by`, set once

The constraint in Decision 6 needs something an index can see, and a partial
index can only see the row's own columns, not the latest audit record. So
`documents` gains `superseded_by UUID NULL REFERENCES documents(id)`.

The architecture rule is that `current_state` is derived from the audit trail,
"never stored as a mutable column". This column is not the state: it is a
pointer, written in the same transaction as the `superseded` audit record, by
one function, and never changed afterwards. A trigger refuses any UPDATE of
`superseded_by` once it is set. Readers get the state from the audit trail as
before, and the pointer only answers "which one survived".

Rejected: a satellite table `document_objects(object_key PK, document_id)` as
the owner of each stored object. It would be a second source of truth for
document identity, and OCR recovery, which already moves a document's
`object_key` to the OCR'd object, would have to move the ownership too.

## Decision 4 — the oldest copy survives

The oldest registered copy of each object survives. Measured: the copies are
interchangeable. Every rank has the same state distribution, and every dossier
membership of a copy is also held by the first. Oldest is the choice that needs
no judgement and gives the same answer on every run.

## Decision 5 — what a superseded document still answers

- `GET /documents/{id}` and its state: `superseded`, with `superseded_by`.
  The id existed, it was cited, and its history is real: a 404 would be false.
- Search: absent. Its index entry is deleted, which needs `delete(doc_id)`
  on the `SearchIndex` protocol; there is none today.
- Dossiers: its memberships are removed through `dossiers.remove`, so each
  removal is a recorded act, actor `dedupe`.
- Reveal: refused, naming the surviving document. A copy is not a second door
  to the same pseudonyms. Its 18,595 pseudonym links stay in place: they are
  facts about what was in it, and the surviving copy has its own.

## Decision 6 — the constraint, in a second release

`CREATE UNIQUE INDEX … ON documents (object_key) WHERE superseded_by IS NULL`
cannot be created while duplicates exist. So there are two releases:

1. The state, the column, the trigger, `SearchIndex.delete`, the readers, and
   the cleanup command. Run the command, dry run first. Its counts have to
   match the ones measured here (173 copies, 159 index entries, 173
   memberships), or it stops and says which differ.
2. The unique index, and registration that loses the race to it adopts the
   existing document (inside a savepoint, the way key minting adopts the
   winner). `init_schema` creates a missing index and nothing else, so the
   second deploy locks `documents` once.

The alternative, an init that creates the index only once no duplicates are
left, would make the constraint appear or not depending on data, silently.

## Decision 7 — OCR recovery can collide, and then it supersedes itself

OCR recovery moves `object_key` to the OCR'd object. If that object already
belongs to a live document, the unique index refuses the move. The recovering
document is then superseded in favour of the one that already holds that
object, the same outcome as if both had been delivered as those bytes.
