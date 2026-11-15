# Design: deleted-document-answers-410

Closes #456. Code references are to origin/main `8577ece`.

## Context

- A document is deleted when the latest record of its audit chain has
  `to_state` `deleted` (`pipeline.current_state`). The row stays, with
  `object_key` `deleted/<id>`; text, pseudonyms, mappings, box map, renders,
  index entry and document-scoped grants are gone.
- Since #485 every route below except the two reveal routes declares the
  corpus-read gate as a dependency, which refuses with 403 before validation
  and before any lookup.
- `audit.append` takes a transaction-scoped advisory lock on the chain
  (`audit.py:42`). The feedback route reads the state before it calls
  `append`, so before it holds that lock.

## Decisions

### 1. Which routes: every route with a document id in its path, decided one by one

| Route | Gate | Answer for a deleted document | Decided by |
|---|---|---|---|
| `GET /documents/{id}/anonymized` | corpus read | 410 | this change |
| `GET /documents/{id}/redacted.pdf` | corpus read (document read after #439) | 410 | this change (was code only) |
| `POST /documents/{id}/feedback` | corpus read | 410, nothing written | this change |
| `GET /documents/{id}/state` | corpus read | 200, state `deleted` | this change, question #501 |
| `GET /documents/{id}` | corpus read | 200, trail with the `deleted` record | this change, question #501 |
| `DELETE /documents/{id}` | delete | 200, finishes leftover work | `document-deletion`, unchanged |
| `POST /documents/{id}/reveal`, `/reveal.pdf` | the grant | uniform 403, or 410 to a covered caller | `reveal-api` via #494, unchanged here |
| `GET /console/documents/{id}` | corpus read | the page opens | `console`, unchanged |

The rule behind the split: a route that returns or accepts the document's
**content** answers 410, because the content is gone for good. A route that
reports the **record of the document** answers, because the record is what a
deletion keeps.

### 2. `/state` and `GET /documents/{id}` keep answering (default of #501)

#456's title says "every per-document route". Taken literally that includes
the two routes that show the state and the audit trail. This change does not
make them 410, for three reasons:

- the `document-deletion` spec promises that the row and the earlier audit
  records remain ("The trail is kept"), and `GET /documents/{id}` is the one
  API route that shows them, the `deleted` record with its caller and counts
  included. A 410 there keeps the promise in the database and breaks it for
  whoever asks;
- the same choice is already made twice: a superseded document answers
  `superseded` with its survivor instead of a 404 (`document-lifecycle`), and
  the console page of a deleted document still opens (`console`);
- a client that gets 410 on a content route needs somewhere to ask "since
  when, by whom". Sending it to the console is no answer for a program.

The alternative (410 on these two as well; the trail then only through the
console and the audit export) is a real choice about what the API promises
after a deletion, and it is Mark's: issue #501, `waiting-on-mark`, default as
written here. If he picks the alternative, the delta is one requirement
("The record of a deleted document stays readable") replaced by two more rows
in the 410 requirement, and two rows in the inventory test.

### 3. The order: gate, unknown, deleted, everything else

1. 401, then the route's gate (403, before validation and lookup, as #485
   built it);
2. 422 for a malformed id or body;
3. 404 for an unknown id;
4. **410 for a deleted document**;
5. the route's other answers (409 superseded, 409 not yet de-identified, the
   box-map answers, the render cache).

"Checked first" in #456 means first among the answers about the document,
not first of all. Before the gate it would tell any caller with a key which
ids were deleted, which is the oracle #485 closed on these routes and #494
closes on the reveal routes.

Deleted wins over superseded: a deleted copy has no content whoever survives
it, and pointing at the survivor suggests the deleted copy's text is there.
`GET /documents/{id}/state` still shows `superseded_by` for it.

The redacted PDF checks before the render cache, as today (#451): a render a
failed cleanup left behind is never served.

### 4. One function decides "deleted", from the state only

A small helper (proposed: `src/wordsworth/document_gone.py`, a few lines)
takes the session and the id, raises 404 for no state and 410 for
`State.DELETED`, and returns the state. The three content routes call it
first in their body; `redacted.pdf` loses its own two checks. One spelling of
the detail, `document deleted`, as the PDF routes use today.

**The clever pitfall, twice.**

- Inferring deletion from what is missing (no text, no box map, an
  `object_key` that starts with `deleted/`). That is what produces today's
  "not yet de-identified": absence has more than one cause. The state is
  derived from the audit chain and from nothing else (architecture
  invariant).
- Making the check a declared dependency next to the gate, because the gate
  looks so tidy that way. FastAPI then runs it for a caller the gate is about
  to refuse, or before the gate if somebody reorders the list, and the 410 is
  an oracle again. It stays a call in the body, after the gate has passed.
  What the declared gate gave for free, a test that sees a missing check, is
  rebuilt by decision 6.

### 5. Feedback is decided under the chain lock

The feedback route reads the state, then appends. A deletion that commits in
between leaves a `detection_feedback` record after the `deleted` record, with
`from_state` and `to_state` the state read before the deletion.
`audit.append` does not check transitions and the state is derived from the
latest record, so the document then reads as `indexed` again while its
content is gone, and every check in this change stops seeing it as deleted
(read from the code, not reproduced). The route therefore decides while
holding the lock `audit.append` takes (take the lock, read the state, refuse
or append, in one transaction). The spec states the result: no
`detection_feedback` record after a `deleted` record, concurrent or not, and
the state stays `deleted`.

Records the deletion itself appends after `deleted` (`destroy-key`,
`remove-renders`, `remove-original-scan`) are not touched: they are the
deletion finishing.

Feedback given before the deletion stays in the trail and in
`/console/feedback`; nothing is removed.

### 6. A test holds the list

`tests/route_rows.py` (from #485) has a row per route. A new table next to it
gives, for every route whose path contains `{document_id}`, the expected
answer for a deleted document: `410`, `record` (200), `rerun` (DELETE),
`reveal-api` (asserted by #494's tests, not here) or `page` (console). The
test walks the application's routes and fails on a `{document_id}` route
without a row, and requests each `410` and `record` row as a reader against a
deleted document. A new per-document route cannot be merged without saying
what it does after a deletion.

### 7. The body says only that it is deleted

`{"detail": "document deleted"}`. Who deleted it and when is in the trail
(`GET /documents/{id}`), behind the same gate; repeating it in every 410
would be a second place to keep right.

## Risks

- **A client that treats 409 on `/anonymized` as "retry later"** now gets 410
  and stops. That is the point; `wordsworth.client` and `console.js` are
  checked in task 4.1 (the console already prints the status and detail of a
  refused feedback).
- **The reveal routes stay inconsistent until #494 is built.** Named so the
  inventory test's `reveal-api` rows are not read as covered by this change.
- **Lock order.** The feedback route takes the chain lock earlier than
  today. It takes no other lock, so there is nothing to order against;
  task 2.3 runs it against a concurrent deletion.

## Found and not changed

- `GET /documents/{id}/anonymized` on a superseded copy serves the copy's
  text without saying it is superseded, unlike the redacted PDF (409).
- The 410 on `redacted.pdf` existed in code without a spec line since #453;
  this change writes it down as it is.
- `openspec/specs/document-deletion/spec.md` has a truncated Purpose line;
  left for an archive pass.

## Open to Mark

1. **#501: do `/state` and `GET /documents/{id}` answer 410 too?** Default:
   no, they keep answering 200 with state `deleted` and the trail
   (decision 2). The change is written on the default.
