# Design: share-recipient-read

Source of the decision: issue #416 (M2), on its default. Code references are
to origin/main `8bbbcec`.

## What widens

One thing. A caller who is **not** on `WORDSWORTH_CORPUS_READ_LABELS` can now
read one document's de-identified content, in two forms, when he is the
recipient of a grant that is in force on that document:

| Surface | Today | After |
|---|---|---|
| `GET /documents/{id}/redacted.pdf` | corpus-read list only (`api.py:711`) | list, or a share on this document |
| `/console/documents/{id}` | corpus-read list only (`console.py:163`) | list, or a share on this document (narrower page, see below) |
| `/console/gedeeld` | does not exist | every logged-in caller, own shares only |

What the recipient reads is what a corpus reader reads of that document: the
redacted PDF (boxes and typed labels, nothing under the box) and the
pseudonymised text with its tokens. No clear PII is added to either. Clear
values stay behind `POST /documents/{id}/reveal`, decided per type by the grant
as today; a grant at PPL 0 reveals nothing and still counts as a share.

Who can cause the widening: only a caller who may issue grants
(`auth.authorize_grant_issue`, the issuer labels). The recipient cannot widen
his own access, and neither can a corpus reader who is not an issuer.

## What does not widen

- Every other route that calls the corpus-read check keeps calling it and
  nothing else: `/documents/{id}/anonymized` (`api.py:678`),
  `/export/anonymized.zip` (873), the topic-label routes (1000),
  `POST /dossiers/{id}/summaries` (1650), and every console page mounted with
  `_mag_lezen` (dossier home, list, search, topics, feedback).
- `GET /documents/{id}/anonymized` stays closed to a recipient although the
  same text is on his document page. Nothing in the share flow links it, and
  one surface fewer is one refusal fewer to keep right. If a recipient needs
  the text over the API, that is a new decision.
- A global grant opens nothing here, also where `allow_global_grants` is on and
  also on the name of the beheerder role. Reading everything is what the
  corpus-read list is for; a second way to it would be the second door.
- The reveal routes. The brief for this change named "the two PDF routes" as
  callers of the new function. The code says otherwise: `POST
  /documents/{id}/reveal.pdf` (`api.py:1512`) has no corpus-read check, it is
  decided by `grants.authorize` alone, exactly like `/reveal` (1382). Adding
  the new check there would be a no-op for a document grant and a **narrowing**
  for the holder of a global grant who is not on the read list. This change
  does not touch it. The callers are the redacted-PDF route and the console
  document page: two, not three.

## The decision

```python
# auth.py, next to authorize_corpus_read
def authorize_document_read(caller, allowed_labels, *, shared: bool) -> bool:
    if authorize_corpus_read(caller, allowed_labels):
        return True
    return bool(caller) and shared
```

Pure, like `authorize_delete`: the function touches no database, and the
caller resolves `shared` (as `_guard_delete` resolves `is_beheerder`). With the
list empty the scope is off and everybody reads, as today. With auth off there
is no caller, `shared` cannot be true, and the answer is the one
`authorize_corpus_read` gives today.

`shared` comes from a new module, `shared_documents.py`:

- `live_shares(caller, now)` builds the one `SELECT` over `grants` joined to
  `documents`: `status == 'active'`, `document_id IS NOT NULL`, recipient
  equal to the caller, `expires_at IS NULL OR expires_at > now`, the role
  either absent or an existing role with `active`, and the document not hidden
  by `console_data.hidden_condition` over `latest_state_subquery`.
- `is_shared(session, caller, document_id, now) -> bool` is that query
  narrowed to one document.
- `listing(session, caller, now) -> list[dict]` is that query grouped per
  document, for the page.

One query for the decision and for the list, so the page cannot list a
document the door refuses, or the other way round.

**Recipient match.** `grants._is_recipient` strips surrounding whitespace on
both sides and compares exactly. The query does the same (trimmed recipient
equals trimmed caller). A test presents the same pairs to both and asserts
they agree; `caller_holds_role` compares without trimming today and is left
alone.

**Expiry.** `grants.authorize` denies at `now >= expires`; the query admits at
`expires_at > now`. Same boundary. The column is `timestamptz`, so the
naive-datetime case `authorize` guards against cannot occur in SQL.

**Role.** A grant naming a role that is switched off or unknown does not count.
A role's types do not matter for reading, but "zet een rol uit" is the
breakglass, and a breakglass that stops the revealing and leaves the reading
would surprise the person pulling it. This is the stricter of two defensible
readings; see "Open to Mark".

**Domain.** Not part of the decision. The domain says which key resolves a
token; reading the redacted document resolves none.

**Hidden documents.** `delete_document` deletes the grant rows of the document
(`deletion.py:174-180`), so a deleted document has no share left. A superseded
copy keeps its grants; the hidden rule excludes it. The console spec says
"opening a single document by its id is not affected" by hiding; that stays
true for a reader on the list. For a recipient it does not apply: a share is
on a live document or it is nothing.

## Order of checks, and what a refusal tells

In `redacted_pdf` the corpus-read check runs before the document is looked up,
so a caller off the list gets 403 for an unknown id and never learns which ids
exist. The new guard keeps that: it runs first inside the session, and for a
caller off the list an unknown, hidden, unshared, revoked and expired document
all give the same 403 with the same detail, "caller not authorized for corpus
read". Only after admission do 404 and 409 exist.

The guard lives in `api.py` next to `_guard_corpus_read`:
`_guard_document_read(request, session, document_id) -> bool`. It raises 403 or
returns whether the admission rested on the share alone. A caller on the list
never reaches the grants query.

## What the server does for a recipient's request

On a cache miss `redacted_pdf` reads the original, renders and stores the
redacted PDF under `redacted/<doc>/<render_version>/<boxmap_hash>`. A
recipient's request can now trigger that. The bytes returned and stored are
the ones a reader's request would produce; nothing recipient-specific is
cached. A document without a box map, or with a stale one, answers 409 to the
recipient as to anyone.

## What the recipient's page shows

`console_data.grants_for` lists every active grant on the document "whoever
they belong to", and `reveal_history` lists who revealed what. For a reader on
the list that is the demonstration. For a recipient it would show the names
(mail addresses, under an identity provider) of everyone else the document was
shared with: more than "that document". So a page admitted by share alone
shows the text, the state, the type counts and the caller's own grants, and
leaves out other recipients' grants, the reveal history, the declared
combinations and the feedback form. The reveal button on his own grant works
as it does today, through `/reveal`.

`base.html` renders seven navigation links that all answer 403 for a
recipient. Pages rendered for a caller who is not on the list show
"gedeeld met mij" and "afmelden" only. `geen_toegang.html` gains one line with
a link to `/console/gedeeld`; it links, it does not say whether anything is
there.

## What is audited

Checked: reading writes no audit record today. `redacted_pdf`
(`api.py:698-763`), `document_anonymized` (666-695) and the console document
page append nothing; the document chain is written by state transitions,
reveals (`deanonymize`), deletions and feedback. A read admitted by a share
therefore writes none either, by the same rule: this change adds no record.

What the trail does hold is the admission: `issue_grant` writes one
`grant_issued` event to the key-lifecycle stream with the recipient, the
document id and the actor, and `revoke_grant` one `grant_revoked`. So the
trail answers "who could read this document, from when until when, and who
let him" and does not answer "did he". That is the same answer it gives for a
reader on the list, where the admission is a line in a configmap and not even
an event. Whether a share read should be recorded is in "Open to Mark".

## Found and not changed

Verified on the local demo as `gast` (logged in, on no list, 2026-11-13).
These routes call no corpus-read check and answered 200:

| Route | Returns |
|---|---|
| `GET /search`, `GET /hybrid` | document ids, scores, object keys |
| `GET /ask` | a generated answer over the pseudonymised passages, with document ids |
| `GET /export/ranking.csv` | rank, document id, score, object key |
| `GET /documents/{id}`, `/documents/{id}/state` | state, timings, PII counts per type, object key |
| `GET /grants/{id}` | recipient, types, document id, for anyone who has the id |

So "no search" is true of what this change opens, and true of the console
(`/console/search` is 403 for a recipient), and **not** true of the API as it
stands: any logged-in caller can already call `/ask`. This change does not
make that wider or narrower. It matters the day a recipient gets his own
login (M4), and it is its own promise change; see "Open to Mark".

## Layout and line counts

| File | Lines now | Change |
|---|---|---|
| `auth.py` | 167 | + `authorize_document_read` (about 20 with its docstring; stays under 200) |
| `shared_documents.py` | new | the query, `is_shared`, `listing` |
| `console_shared.py` | new | `mount(...)`: `/console/gedeeld` |
| `console_document.py` | new | the document page, moved out of `console.py` |
| `console.py` | 233 | shrinks: the document page (lines 160-190) moves out; two `mount` calls and one parameter come in |
| `api.py` | 2009 | `_guard_document_read` next to `_guard_corpus_read`; one changed call in `redacted_pdf`; one argument to `build_router` |
| `templates/gedeeld.html` | new | |
| `templates/document.html`, `base.html`, `geen_toegang.html` | | conditionals and one link |

`api.py` and `console.py` are over 200 already; they change at call sites
only, and `console.py` gets smaller. `_declared` stays in `console.py` and is
passed to `console_document.mount`. Tests go in new files
(`tests/test_console.py` is 518 lines).

## Open to Mark

Working assumptions, each overrulable:

1. **A read admitted by a share writes no audit record** (as no read does).
   The alternative is one access record per request on the document chain,
   with from-state equal to to-state as feedback does; it would also be the
   first read that is recorded, so a reader on the list would be less visible
   than a recipient.
2. **A role that is switched off takes the reading away too.** The alternative:
   reading rests on the grant alone and only revoking ends it.
3. **The recipient's page hides other recipients and the reveal history.**
4. **The API routes in "Found and not changed" stay as they are in this
   change.** Proposed separately: put them behind the corpus-read check before
   anyone who is not a corpus reader gets a login.
