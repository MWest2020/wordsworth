# Hide deleted documents in the console by default

## Why

Mark, by mail: *"I only see deleted files, there needs to be a filter."* The
console list shows every document row. A deletion keeps the `documents` row
(document-deletion), so a corpus that has been cleaned up shows mostly deleted
documents and hides the ones worth reading.

The console already hides superseded copies on its first page (the list filters
on `superseded_by`), but it does so without saying so and without a way to see
them, and it does not hide deleted documents at all. The search and topics pages
have no stated rule.

This changes what the console shows by default, so it is an OpenSpec change.

## What changes

- The console document list, the search page and the topics page hide documents
  whose state is `deleted`, and superseded copies, by default.
- An explicit toggle on each page shows them. Showing them is a choice the
  reader makes, never the default.
- A page that is hiding documents says so, so an empty or short result is not
  read as "the corpus is small".
- A test per page: list, search and topics, each proving the default hides and
  the toggle shows.

Not changed: the document page (`/console/documents/{id}`) still opens any
document by id; the API; what deletion and superseding do to the index and the
trail.

## Open questions

- What the toggle looks like (a checkbox, a link) and what it is called in the
  query string. The decision says "an explicit toggle", nothing more.
- What the toggle means on search and topics. Deletion and superseding already
  remove a document's index entry, and search hits and topic membership come
  from the index. The decision does not say whether the toggle there can show
  anything, or whether the rule on those pages only guards against a stale
  entry. Left to Mark.
- Whether the "hidden" notice states the count per state or one total.
