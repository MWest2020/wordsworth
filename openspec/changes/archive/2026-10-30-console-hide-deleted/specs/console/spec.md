## ADDED Requirements

### Requirement: Deleted and superseded documents are hidden unless asked for

The console document list SHALL hide documents whose state is `deleted`, and
superseded copies, by default. The list SHALL offer an explicit toggle that
shows them.

A deletion keeps the document's row, so a cleaned-up corpus shows mostly what
was removed and buries what is worth reading. Showing the hidden documents is
a choice the reader makes, not what they get when they say nothing.

A list that is hiding documents SHALL say so, with one total. A list that
silently leaves rows out reads as the whole corpus.

The console search page SHALL NOT show a hit for a deleted or superseded
document and offers no toggle for it: deletion and superseding already remove
the index entry, so the rule there only guards against a stale entry.

Opening a single document by its id is not affected: that is an explicit
request for that document.

#### Scenario: The list hides deleted and superseded documents

- **WHEN** an operator opens `/console` and the corpus holds a live, a deleted
  and a superseded document
- **THEN** only the live document is listed, the total counts only live
  documents, and the page says documents are hidden

#### Scenario: The toggle shows them on the list

- **WHEN** the operator turns the toggle on
- **THEN** the deleted and the superseded document are listed too, with their
  state

#### Scenario: Search never shows a hidden document

- **WHEN** the search index holds a stale entry for a deleted document
- **THEN** the hit is not shown, and search offers no toggle to show it

#### Scenario: A list with nothing hidden does not claim otherwise

- **WHEN** the list shows a corpus without deleted or superseded documents
- **THEN** it shows no notice that documents are hidden

#### Scenario: A deleted document can still be opened by id

- **WHEN** an operator requests `/console/documents/{id}` for a deleted document
- **THEN** the page answers as it did before this change
