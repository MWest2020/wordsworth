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

A caller on the corpus-read list SHALL see the page as before, also when a
document was shared with him as well.

#### Scenario: Another recipient's grant is not shown

- **WHEN** document D is shared with two recipients and one of them opens its
  page
- **THEN** the page shows his own grant and not the other recipient's name or
  grant

#### Scenario: No link on the recipient's pages is a dead end

- **WHEN** a recipient opens "Gedeeld met mij" and then a shared document's
  page
- **THEN** every link on both pages answers below 400 for him

#### Scenario: A reader on the list keeps the full page

- **WHEN** a caller on the corpus-read list opens a document that was also
  shared with him
- **THEN** the page shows every active grant and the reveal history, as before
