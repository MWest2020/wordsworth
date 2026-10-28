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
- **One rule, shared by the three pages.** The filter lives in one helper in
  `console_data.py` rather than being written three times; three copies would
  drift, and the next page would forget it.
- **Say that something is hidden.** A list that silently omits rows reads as the
  whole truth. The page shows that documents are hidden and how to see them.
  This also fixes the existing silent hiding of superseded copies.
- **The document page is unchanged.** Asking for one document by id is an
  explicit act; a deleted document answers as it does today.

## Rejected alternatives

- **Default shows everything, with a filter to hide.** What Mark found; the
  default is what most readers get, and it buried the live documents.
- **Hide only deleted, leave superseded.** Superseded copies fill the list the
  same way (one-document-per-object); the decision names both.
- **Filter in the template.** A page limited to 200 rows would then show fewer
  than 200 live documents and a wrong total. The filter belongs in the query.
- **A stored "hidden" flag.** A second source of truth for state.
