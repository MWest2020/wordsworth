## ADDED Requirements

### Requirement: Deleted and superseded documents are hidden unless asked for

The console document list, the search page and the topics page SHALL hide
documents whose state is `deleted`, and superseded copies, by default. Each of
those pages SHALL offer an explicit toggle that shows them.

A deletion keeps the document's row, so a cleaned-up corpus shows mostly what
was removed and buries what is worth reading. Showing the hidden documents is
a choice the reader makes, not what they get when they say nothing.

A page that is hiding documents SHALL say so. A list that silently leaves rows
out reads as the whole corpus.

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

#### Scenario: Search leaves hidden documents out

- **WHEN** a search would return a hit for a deleted document
- **THEN** the hit is not shown by default, and is shown when the toggle is on

#### Scenario: Topics do not count hidden documents

- **WHEN** the topics page is shown for a dossier that holds deleted or
  superseded documents
- **THEN** by default they are neither listed nor counted, and with the toggle
  on they are

#### Scenario: A page with nothing hidden does not claim otherwise

- **WHEN** a page shows a corpus without deleted or superseded documents
- **THEN** it shows no notice that documents are hidden

#### Scenario: A deleted document can still be opened by id

- **WHEN** an operator requests `/console/documents/{id}` for a deleted document
- **THEN** the page answers as it did before this change
