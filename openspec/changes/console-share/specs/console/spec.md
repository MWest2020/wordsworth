## ADDED Requirements

### Requirement: The console shares and shows what the recipient can open

The console SHALL offer "Delen" on the document, topic and dossier pages to a
caller who may issue grants, and SHALL NOT offer it to anyone else. Sharing
from the console SHALL go through the same gate, the same issue function and
the same audit as `POST /grants`. The console SHALL add no widening: a share
may only narrow what `POST /grants` allows.

After sharing, the console SHALL show a result page naming the recipient
exactly as stored, the number of grants issued, and per document a link to its
console page and, where a redacted PDF can exist, to that PDF. The page SHALL
say that the recipient must be logged in under exactly that name, and that
values above PPL 0 are revealed under the recipient's own login. The links
SHALL be ones the recipient can open; that rests on the recipient's right to
read a shared document (change `share-recipient-read`).

The console SHALL list the shares, the most recent 200 with the total, and
SHALL let an issuer revoke one from its page.

A refusal SHALL be a page a person can act on. When sharing a topic fails
because the index is unreachable, a browser SHALL get an HTML page with the
form and the message. When a caller who may read the corpus is refused because
he is not an issuer, the page SHALL say that, and SHALL NOT tell him he is not
on the read list.

#### Scenario: The result page lists what was shared

- **WHEN** an issuer shares a dossier from the console
- **THEN** the result page states the recipient and the number of grants, and
  lists every shared document with a link to its page

#### Scenario: The recipient opens a link from the result page

- **WHEN** the recipient, who is not on the corpus-read list, requests a
  document link taken from the result page
- **THEN** the answer is 200, and 403 after the share is revoked

#### Scenario: A document without a redacted PDF says so

- **WHEN** a shared document has no box map
- **THEN** the result page links its console page and says there is no
  redacted PDF yet, instead of a link that answers 409

#### Scenario: Delen is offered only to an issuer

- **WHEN** a caller who may read the corpus but is not an issuer label opens a
  document, a topic list or a dossier
- **THEN** the page offers no "Delen", and requesting the share form directly
  answers 403

#### Scenario: A reader who is not an issuer is told the right thing

- **WHEN** a caller on the corpus-read list who is not an issuer label requests
  the share form in a browser
- **THEN** the answer is 403 with a page that names him and says he may not
  share, and that does not say he is missing from the read list

#### Scenario: The index is unreachable, in a browser

- **WHEN** an issuer shares a topic from the form while the index cannot be
  reached
- **THEN** the answer is 503 as an HTML page showing the form and the message
  that nothing was shared
