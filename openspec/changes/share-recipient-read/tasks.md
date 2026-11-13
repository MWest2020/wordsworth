# Tasks

Tests use three callers with their own API keys: `lezer` (on the corpus-read
list), `ontvanger` (the recipient) and `derde` (logged in, on no list, no
grant). Every refusal below is asserted as `ontvanger` or `derde`, never as
`lezer`: the side that does not hold the key.

## 1. The decision
- [ ] `auth.authorize_document_read(caller, allowed_labels, *, shared)`.
      Proved by: a unit test of the truth table (on the list; off the list and
      shared; off the list and not shared; no caller and `shared=True`; empty
      list).
- [ ] `shared_documents.is_shared(session, caller, document_id, now)` over the
      one query. Proved by: one database test per row of: active document
      grant (true), revoked, expired at the boundary (`now == expires_at` is
      false, one second earlier is true), no document scope, another
      document, another recipient, a recipient differing in case, a recipient
      that is a prefix, a superseded copy, a deleted document, a role switched
      off, an unknown role, a role switched back on (true).
- [ ] The recipient is decided by `grants._is_recipient` in Python, after the
      SQL filters; no recipient comparison in SQL. Proved by: the rows above
      for case and prefix (false), a row for a stored recipient with
      surrounding whitespace (true), and the diff.
- [ ] Several grants on one document. Proved by: a test that a revoked grant
      plus a newer active one is true, and that two active grants are true and
      one row in `listing`.
- [ ] `now` is an argument everywhere; no `func.now()`. Proved by: the expiry
      boundary test passing two times one second apart without sleeping, and
      `grep -n "func.now" src/wordsworth/shared_documents.py` empty.

## 2. The two callers
- [ ] `GET /documents/{id}/redacted.pdf` calls `_guard_document_read` inside
      its session, before the document is looked up. Proved by: API tests as
      `ontvanger`: 403 before the grant, 200 and `%PDF` after, 403 on a
      neighbour in the same dossier, 403 after revoke, 200 after a new grant
      is issued following that revoke, 403 after expiry, 403
      with only a global grant where `allow_global_grants=True`, 403 for an
      unknown id; and as `derde`: 403 on the shared document.
- [ ] The console document page calls the same guard. Proved by: the same list
      of cases against `/console/documents/{id}`, as `ontvanger` and `derde`.
- [ ] A refusal does not tell the cases apart. Proved by: a test that the 403
      body is identical for unknown, unshared, revoked, expired and superseded.
- [ ] Nothing else opened. Proved by: one parametrised test as `ontvanger`,
      holding an active grant, that each of `/console`, `/console/documents`,
      `/console/dossier?dossier=…`, `/console/search`, `/console/topics`,
      `/console/feedback`, `/console/roles`, `GET /documents/{id}/anonymized`,
      `/export/anonymized.zip` and `POST /dossiers/{id}/summaries` answers 403.
- [ ] A reader on the list is unaffected. Proved by: the existing suite
      unchanged and green, plus a test that `lezer` gets 404 from
      `GET /documents/{id}/redacted.pdf` for an unknown id (the console
      document page has no 404: it renders "Geen gepseudonimiseerde tekst opgeslagen" for a
      reader, as today) and the full page for a document also shared with him.
- [ ] `POST /documents/{id}/reveal.pdf` is untouched. Proved by: the diff, and
      `tests/test_reveal_pdf_api.py` unchanged and green.

## 3. The pages
- [ ] `/console/gedeeld` for every logged-in caller. Proved by: a test with
      one caller holding a live grant, a revoked one, an expired one, one on a
      deleted document, one on a superseded copy and a global one: exactly one
      row; and a test that `derde` gets an empty list that says so and names
      the caller.
- [ ] The recipient's document page: own grants only, no reveal history, no
      declared combinations, no feedback form. Proved by: a test with two
      recipients on one document asserting the other's label is absent from
      the HTML, and a test that the page of `lezer` still has all of it.
- [ ] The recipient's own grants come from `shared_documents`, not from the
      50-row `grants_for`. Proved by: a test with 60 grants to other
      recipients issued after his: his page shows his grant and its reveal
      button.
- [ ] No filename for a recipient. Proved by: a test with a document whose
      filename holds a seeded name: the string is absent from the recipient's
      document page (title included) and from his "Gedeeld met mij", both show
      `document <hash8>`, and the page of `lezer` still shows the filename.
- [ ] No dead end. Proved by: a test that collects every `href` on the
      recipient's "Gedeeld met mij" and document page and requests each as
      `ontvanger`: all below 400.
- [ ] The 403 page links `/console/gedeeld`. Proved by: a test as `derde` on
      `/console` with `Accept: text/html`.
- [ ] `console.py` is smaller than 233 lines and no new file exceeds 200.
      Proved by: `wc -l` in the PR.

## 4. Docs
- [ ] `docs/how-to/grants.md`: a document grant also lets its recipient read
      that document; what it does not open; the outdated "no caller
      authentication yet" caveat goes (a grant has named its recipient since
      `authorize` checks the caller). `docs/how-to/local-demo.md`: the walk
      below. Front matter `status`, `last_reviewed`.

## 5. Local check

Run after #437 is fixed (until then a real browser cannot post the console
login form, and the walk below would be curl only) and after #442 is closed
(until then `gast` also reaches `/search`, `/ask` and the other routes of
#442, and the walk would show a narrower door than there is). Step 5 then
also includes `GET /search`, `/hybrid` and `/ask` as `gast`: 403 each.
- [ ] In the harness (`tools/demo/serve_local.py --reset`), with the printed
      keys, as a browser would (cookie from `/console/login`,
      `Accept: text/html`). Proved by: the status codes pasted in the PR.
      0. The walk is done once with curl and once in a real browser with two
         profiles (`mark`, `gast`).
      1. `gast`: `GET /documents/{D}/redacted.pdf` 403; `/console/documents/{D}` 403.
      2. `mark`: `POST /grants` `{recipient: "gast", ppl: 0, document_id: D}` 201.
      3. `gast`: both 200 (`%PDF`); `/console/gedeeld` lists D and only D,
         as `document <hash8>` and not by its filename.
      4. `gast`: a neighbour of D in the demo dossier 403, PDF and page.
      5. `gast`: `/console/search` 403; `/console` 403 with a link to
         `/console/gedeeld`.
      6. `mark`: `POST /grants/{id}/revoke`; `gast`: PDF and page 403,
         `/console/gedeeld` empty.
- [ ] `/security-review` on the diff, clean or every finding answered in the
      PR.
