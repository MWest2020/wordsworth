---
status: draft
last_reviewed: 2026-09-17
---

# Reading the console

A screen for looking at what the pipeline produced: the documents, the
pseudonymised text with its tokens marked, and the combinations of PII types
someone judged to identify together.

## Running it

The console is mounted **only when API-key authentication is configured**. A
screen that lists every document and the PII types found in it does not belong
on an open port, and no screen beats a screen without a lock.

```bash
export WORDSWORTH_API_KEYS="mark:<key>"
uvicorn wordsworth.serve:app
```

Then open the hostname. Anything you type lands somewhere useful: `/` goes to
the console, an unknown path goes to the console, and any page you are not
logged in for goes to `/console/login`. Enter the key there; it is stored in an
HttpOnly, SameSite=strict cookie for eight hours. `/console/logout` clears it.

A wrong key is refused at the form, not stored — otherwise a typo hands you a
cookie that leads back to the same refusal, with the added confusion of having
apparently logged in.

Only a request that asks for HTML is redirected. An API client keeps getting the
unchanged 401 with its JSON body: a program handed a 303 to an HTML form will
try to parse the form.

The cookie is a second **transport** for the key, not a second check: the same
middleware, the same key set, the same caller label. With an identity provider in
front (see [access identity](access-identity.md)), a presented key still wins —
logging in here is how you choose the key route, and `/console/logout` hands the
identity back. A browser cannot set
`X-API-Key` on a plain navigation, and putting the key in a query string would
leak it into logs, history and referrers.

`/console/login` is exempt from authentication — you cannot bring a key to the
page that asks for one — and stays subject to rate limiting, because that is the
one route where guessing pays.

## What the pages show

**`/console`** lists documents by the name they arrived under, with their state
and the PII types found, most recently touched first. A document ingested before
names were recorded shows as `naamloos (<first 8 of the hash>)` —
`wordsworth-backfill-filenames` can give those their names back where the files
are still on disk. The full content hash is never shown as if it were a name. The types come from the pseudonyms the pipeline *minted*
per document, not from re-running the detectors over the source text: that would
answer "what would the detectors say today", which is a different question from
"what did the pipeline do".

**`/console/documents/{id}`** shows the stored pseudonymised text with each token
marked and labelled, plus which declared combinations the document carries in
full and which it leaves untouched.

**`/console/combinations`** is where a combination is *established*. Record two
or more types with a reason, and the page shows immediately in how many
documents every one of those types occurs. Establishing which types identify
together depends on the population and the context, so it is the judgement of
whoever reads the documents — a rule that lives only in a file a developer edits
is established by nobody.

A type no detector emits is marked **"niet te zien"** rather than counted as
zero. That zero would read as "does not occur" when the answer is "cannot be
established here".

## Look and feel

The console carries the same design as the public demo
(`MWest2020/wordsworth-demo`): the same palette in light and dark, the same
families, the same token chips. Two different looks for one story is a missed
opportunity, and it makes the working thing look less finished than the
illustration of it.

The fonts are served from `/console/static`, not from a CDN. This is the screen
where wordsworth's claim to sovereignty is demonstrated and also the screen
people inspect; a page fetching its letters from Google refutes that claim in the
network inspector, whatever the surrounding text says. Nine Latin faces, 224 KB.

That subtree is reachable without a key — the login page is too, and a login
screen rendered without its letters is a broken door. The exemption covers that
subtree only.

## Searching

`/console/search` runs over the same index the API serves, **within a dossier**.
Picking one is compulsory; "alle dossiers" is possible but has to be said. A
forgotten scope must never mean the widest possible answer — that is the whole
point of scoping.

It shows per hit its score and a fragment **of the stored pseudonymised text**. A fragment taken from
a source document would look identical and prove the opposite of what this page
is for.

The offered terms are examples, not a promise: whether one matches depends on the
corpus that happens to be loaded. A term with no hits says so; an index that is
down says *that*, rather than returning an empty list that reads as "nothing
matched".

## Revealing

The document page lists the **active** grants that apply to it — including grants
issued to someone else. That is deliberate: the screen offers it, the door refuses it, and
watching the refusal is the demonstration that the keys are role-bound.

Revoked grants are counted, not listed. One authorises nothing, and a row per
piece of history buries the grant that can actually be used — six dead ones from
a test in August did exactly that. The count stays, because "revocable" is half
the claim and a screen showing no trace of it quietly drops that half.

Per grant there is a switch per PII type. These are not decoration: the reveal
request carries the checked types and `authorize()` intersects them with the
grant.

The page has no way out of its own. Revealing calls the existing
`POST /documents/{id}/reveal` with the cookie you already hold — the same
`authorize()`, the same recipient binding, the same audit record as for any
other caller. There is no authorisation code, no key handling and no separate
trail in the console. The rule that matters is not "the console must not reveal"
but "the console must not have a second door".

The document's reveal history sits under the button. An audit trail nobody looks
at is a promise, not a control; putting it on the same page is what makes it one.
It separates **resolved** from **requested**: a token minted under a key this
deployment no longer holds resolves to nothing, and one list would make that look
identical to a reveal nobody asked anything of.

## Marking which value was revealed

After a reveal the page marks which value replaced which token. It works that
out by anchoring on the literal text around them, which does not change.

If there is **more than one way** to read the text, it marks nothing and shows
the revealed text plain. That case is real: when a revealed value happens to
contain the same literal that follows it, the old code took the first match and
labelled `Piet over 123456782` as a BSN. The reader is there to judge whether the
pseudonymisation is right, so a wrong label is worse than none.

## What the browser is allowed to do with it

The console sends `Content-Security-Policy` with `frame-ancestors 'none'`, plus
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and
`Referrer-Policy: no-referrer`. Only on `/console` — the API has no browser and
would get nothing from a CSP but surprises.

Framing is the one that matters. Without it, someone can put
`/console/documents/<id>` in an invisible iframe and slide the reveal button
under a cursor. They cannot read the answer — CORS is closed — but **the reveal
happens, and the audit trail names the victim**. An append-only trail with a
false name in it cannot be repaired.

A cross-site `POST` to `/console` is refused on its `Origin`. Logging in is what
sets the caller label, so a page elsewhere could otherwise switch a visitor's
label to a key the attacker knows: not a privilege gain — it is someone else's
key — but false attribution, and `Path=/` makes it apply to the whole API.

A request with no `Origin` at all is allowed. curl, the CLI and the tests send
none, and locking them out would cost more than the hole. That is also the limit
of this defence: it stops a browser, not a script — and a browser is exactly what
the hole needed.

## What it deliberately cannot do

It reads the corpus through the same gate as `/documents/{id}/anonymized` and
`/export`: a caller that `WORDSWORTH_CORPUS_READ_LABELS` refuses there is refused
here. Until 2026-09-18 it was not, which made the console precisely the second
door its own docstring forbids.

It never reveals on its own authority. Re-identification has exactly one door: the grant-gated,
audited `reveal` endpoint (see [grants](grants.md)). An inspection screen that
may also reveal is a second door with a friendlier name, and it is the one
nobody audits.

It does not edit documents, and it cannot issue grants — that right belongs to
the issuer labels. When a document has no grant, the page says so and says how to
make one.

## A caveat worth seeing on screen

If the deployment runs without the GLiNER/OpenAnonymiser layer, names stay in
the clear in the stored text — and the console shows them, because it shows what
the pipeline actually produced. That is the same finding as the `PERSON` leaks
in [the evaluation](../reference/evaluation.md): a property of that deployment,
not of the screen.
