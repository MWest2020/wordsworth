# Design

## Context

`console.py` lists documents with `Document.superseded_by IS NULL`, so superseded
copies are already hidden on `/console`, silently. A deleted document keeps its
row and is not filtered. `documents.current_state` is not stored: the state is
derived from the latest audit record (`audit.current_state`).

## Choices

- **Default hides, the toggle shows.** The decision. The reader who wants the
  history asks for it; the reader who wants the corpus is not made to ask.
- **Hidden means state `deleted` or superseded.** Both come from the same place
  as everywhere else: the derived state and `superseded_by`. No new column and
  no stored flag, which would be a mutable copy of what the trail already says.
- **One rule, shared by list and search.** The filter lives in one helper in
  `console_data.py` rather than being written twice; copies would drift. On the
  list it is a query condition; on search it is only a guard against a stale
  index entry.
- **Say that something is hidden.** A list that silently omits rows reads as the
  whole truth. The page shows one total of hidden documents and how to see them,
  not a count per state. This also fixes the existing silent hiding of
  superseded copies.
- **Search has no toggle.** Deletion and superseding remove the index entry, so
  a toggle would show nothing. A stale entry is a defect to hide, not a choice to
  offer. Working assumption; Mark can overrule it later.
- **Topics are untouched.** The page shows the persisted `Topic.document_count`
  from the last `topics.compute` run and lists no documents.
- **The document page is unchanged.** Asking for one document by id is an
  explicit act; a deleted document answers as it does today.
- **Toggle form and query-string name** are the builder's call.

## Rejected alternatives

- **Default shows everything, with a filter to hide.** What Mark found; the
  default is what most readers get, and it buried the live documents.
- **Hide only deleted, leave superseded.** Superseded copies fill the list the
  same way (one-document-per-object); the decision names both.
- **Filter in the template.** A page limited to 200 rows would then show fewer
  than 200 live documents and a wrong total. The filter belongs in the query.
- **A stored "hidden" flag.** A second source of truth for state.
- **Re-derive topic counts per request.** A new index query per topic and a
  second meaning for `computed_at` (when the topics were computed versus when
  the count was taken). A separate change.
- **A toggle on search.** Nothing to show behind it.
