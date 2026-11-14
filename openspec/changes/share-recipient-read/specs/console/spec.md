## ADDED Requirements

### Requirement: A caller sees what was shared with him

The console SHALL offer a page, "Gedeeld met mij", to every logged-in caller,
listing the documents shared with that caller and no other document. A
document SHALL be listed only while a grant on it counts as a share for this
caller: active, not expired, scoped to that document, on a live document. The
page SHALL list all of them, with their number, and SHALL say so when there are
none. It SHALL show the name the caller is logged in under, because a share
names its recipient exactly and a recipient who logged in under another name
sees an empty page.

Each row SHALL link the console page of that document. The page SHALL NOT show
a document shared with somebody else, nor how many documents the corpus holds.

#### Scenario: The list shows only live, shared documents

- **WHEN** a caller holds an active grant on document A, a revoked grant on B,
  an expired grant on C, an active grant on a deleted document, an active grant
  on a superseded copy, and a grant without a document scope
- **THEN** "Gedeeld met mij" lists A and nothing else

#### Scenario: Two grants on one document are one row

- **WHEN** a caller holds two active grants on document A, or a revoked grant
  and a newer active one
- **THEN** "Gedeeld met mij" lists A once

#### Scenario: Somebody else's share is not listed

- **WHEN** document D is shared with one caller and a third caller opens
  "Gedeeld met mij"
- **THEN** the third caller's page lists nothing and says so

#### Scenario: A refusal points to the page

- **WHEN** a logged-in caller who is not on the corpus-read list opens
  `/console` in a browser
- **THEN** the answer is the 403 page, and it links "Gedeeld met mij"

### Requirement: A recipient's document page shows that document and nobody else

When a caller is admitted to a document page by a share and not by the
corpus-read list, the page SHALL show the document's pseudonymised text, its
state, its type counts and the caller's own grants on it. It SHALL NOT show
grants issued to other recipients, the reveal history, the declared
combinations or the feedback form. It SHALL NOT carry a link that answers 403
for this caller.

The page, its title and the "Gedeeld met mij" list SHALL NOT show such a
caller the document's original filename. They SHALL name the document by the
word "document" and the first eight characters of its content hash. A filename
is not pseudonymised, and filenames of Woo files often hold names.

A caller on the corpus-read list SHALL see the page as before, filename
included, also when a document was shared with him as well.

#### Scenario: Another recipient's grant is not shown

- **WHEN** document D is shared with two recipients and one of them opens its
  page
- **THEN** the page shows his own grant and not the other recipient's name or
  grant

#### Scenario: A recipient does not see the filename

- **WHEN** a document whose filename holds a person's name is shared with a
  caller who is not on the corpus-read list, and he opens "Gedeeld met mij" and
  the document's page
- **THEN** neither page, title included, contains the filename; both name the
  document by its hash, and a reader on the list still sees the filename

#### Scenario: No link on the recipient's pages is a dead end

- **WHEN** a recipient opens "Gedeeld met mij" and then a shared document's
  page
- **THEN** every link on both pages answers below 400 for him

#### Scenario: A reader on the list keeps the full page

- **WHEN** a caller on the corpus-read list opens a document that was also
  shared with him
- **THEN** the page shows every active grant and the reveal history, as before

## MODIFIED Requirements

### Requirement: A document's reveal history is visible without its values

The console SHALL show, for a document, the reveals recorded against it: when,
by whom, under which grant and which types. It SHALL NOT show any revealed
value.

An audit trail nobody looks at is a promise, not a control. Putting it on the
same page as the reveal button is what makes it one.

The history SHALL be shown to a caller on the corpus-read list. It SHALL NOT be
shown to a caller admitted to the page by a share alone: it names every caller
who revealed on the document, which is more than the one document that was
shared with him.

#### Scenario: The trail names types and never values

- **WHEN** a document's reveal history is shown
- **THEN** each entry names the caller, the grant and the types, and contains no
  PII value

#### Scenario: A recipient does not see the trail

- **WHEN** a caller admitted by a share alone opens the page of a document on
  which another caller has revealed
- **THEN** the page shows no reveal history and does not name that caller

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

Opening a single document by its id is not affected for a caller on the
corpus-read list: that is an explicit request for that document. A caller who
is admitted by a share alone SHALL be refused a hidden document with 403: a
share is on a live document or it is nothing.

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

#### Scenario: A hidden document is not opened through a grant

- **WHEN** a caller who is not on the corpus-read list holds an active grant
  on a superseded copy and requests `/console/documents/{id}` for it
- **THEN** the answer is 403
