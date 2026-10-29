# Hide deleted documents in the console by default

## Why

Mark, by mail: *"I only see deleted files, there needs to be a filter."* The
console list shows every document row. A deletion keeps the `documents` row
(document-deletion), so a corpus that has been cleaned up shows mostly deleted
documents and hides the ones worth reading.

The console already hides superseded copies on its first page (the list filters
on `superseded_by`), but it does so without saying so and without a way to see
them, and it does not hide deleted documents at all.

The first version of this change also covered the search and topics pages. The
architect failed it (wordsworth#277): deletion and superseding already remove a
document's index entry, so there is nothing on those pages for a toggle to show,
and the topics page lists no documents at all. The scope is cut to what is real.

This changes what the console shows by default, so it is an OpenSpec change.

## What changes

- The `/console` document list hides documents whose state is `deleted`, and
  superseded copies, by default. This is the whole build.
- An explicit toggle on that page shows them. Showing them is a choice the
  reader makes, never the default.
- When the list is hiding documents it says so, with one total, so an empty or
  short list is not read as "the corpus is small".
- Search: no toggle. Deletion and superseding already remove the index entry, so
  there is nothing to show. The rule on `/console/search` is only a guard
  against a stale index entry. Its test builds a stale entry by hand and proves
  the guard; it does not claim that deletion leaves hits behind.
- Topics: out of scope. The page shows the persisted `Topic.document_count` from
  the last `topics.compute` run and lists no documents. Re-deriving it per
  request would be a new index query per topic and a second meaning for
  `computed_at`; that is a separate change. The spec makes no per-request
  promise there.

Not changed: the document page (`/console/documents/{id}`) still opens any
document by id; the API; what deletion and superseding do to the index and the
trail; the topics page.

## Open questions

- Search: "no toggle, guard only" is a working assumption. Mark can overrule it
  later.
- Topics: whether to re-derive `document_count` per request so that hidden
  documents are excluded is a separate change, not decided here.

Settled, so not open: the toggle form and its query-string name are the
builder's call, and the notice states one total.
