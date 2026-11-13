---
status: draft
last_reviewed: 2026-11-13
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

Only a path that matches **no route** is redirected. A 404 that a route itself
answers — an unknown document, an unknown grant — stays a 404, also for a
browser: it is an answer about what you asked for, and hiding it behind a
redirect makes "does not exist" invisible and lets a monitoring check read the
303 as healthy.

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

Exempt from authentication, but not blind: it can still read the same verified
assertion the middleware would use (see [access identity](access-identity.md)).
Someone the identity provider already knows is sent straight on to `/console`
instead of seeing the key form; `?key=1` always shows the form anyway, so the
key route stays reachable. With no identity provider configured, or no
assertion on the request, the form shows as before.

## What the pages show

**`/console`** starts on a dossier. It lists every dossier with its number of
live documents (deleted and superseded ones are not counted) and its number of
topics. An installation with exactly one dossier has nothing to choose, so
`/console` answers `303` straight to that dossier's page. With none, the page
says so and links the full list.

**`/console/dossier?dossier=<name>`** is the dossier page. The dossier is a
query parameter, like on every other console page, and not a path segment:
names are free text, and a name with a slash would match no route as a path, so
the answer that lists the dossiers could never be reached for it. Encode the
name (`a/b` is `?dossier=a%2Fb`, `a b` is `?dossier=a%20b`); the console's own
links already do. The page shows:

- a question box that searches this dossier (`/console/search?dossier=…`);
- the dossier's topics, largest first, with their number of documents and a
  link that searches within the topic (`&topic=<id>`), plus one line saying how
  many of the live documents fall in a topic at all (a topic list that covers
  under half the dossier would otherwise read as the whole dossier). The count
  per topic is from the last computation. When the topics count more documents
  than the dossier now holds, documents were deleted since; the page says so
  and links the topics page to compute them again, rather than showing a
  fraction above one or clamping it;
- its live documents, most recently touched first, with the same 200-row cap,
  hidden-documents notice and `&alles=1` toggle as the full list below.

An unknown name answers `404` with the list of dossiers that do exist, not an
empty page: an empty page for a typo reads as "this dossier holds nothing". No
name at all (`/console/dossier`, `?dossier=`) answers `303` to `/console`, where
a dossier is chosen.

A dossier name may contain a comma. A search scope (`/console/search?dossier=`
and the API's `GET /search?dossier=`) is first tried as one whole name and only
then read as a comma-separated list, so the dossier `a,b` searches itself and
not `a` and `b`. With no dossier named `a,b`, `a,b` still means both.

**`/console/documents`** ("alle documenten") is the full list that used to be
the home page, kept for operators: every document across all dossiers, by the
name it arrived under, with their state
and the PII types found, most recently touched first. A document ingested before
names were recorded shows as `naamloos (<first 8 of the hash>)` —
`wordsworth-backfill-filenames` can give those their names back where the files
are still on disk. The full content hash is never shown as if it were a name. The types come from the pseudonyms the pipeline *minted*
per document, not from re-running the detectors over the source text: that would
answer "what would the detectors say today", which is a different question from
"what did the pipeline do".

A deletion keeps a document's row (see below), and a superseded copy is a
retired row of the same object (`wordsworth-supersession`), so by default the
list hides both: documents whose state is `deleted`, and superseded copies. A
cleaned-up corpus would otherwise show mostly what was removed and bury what is
worth reading. `?alles=1` (`/console/documents?alles=1`) is the explicit toggle that shows them too, with their
state; the total in the badge follows the same rule as the rows underneath it.
When something is hidden the page says so, with one total and a link to the
toggle — a list that silently leaves rows out reads as the whole corpus. A list
with nothing hidden shows no such notice.

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

It shows per hit a quotation **of the stored pseudonymised text**. A quotation
taken from a source document would look identical and prove the opposite of what
this page is for. The score is a tooltip on the document link (`title`), no
longer a column: it is a fused rank value and invites comparisons it does not
support.

### Why a result matched

For each of the **first ten hits** on the page, the console shows **the passage
of the document closest to the question** (change search-matching-passage). It
reads the stored passage vectors of those ten documents from the index
(`SearchIndex.passages_of`, one `mget` on OpenSearch), embeds the question a
second time with the same embedder, and takes the passage with the highest
cosine. The passage is cut from the stored text by offset
(`passages.split_spans`), so it is a substring of it, and trimmed for the row:
a window around its first marked word, or its opening when nothing is marked,
with "…" where it was cut. The order of the hits does not change, and nothing
new is stored. See [why a result matched](../explanation/why-a-result-matched.md)
for what "closest" does and does not mean.

The reason under the passage says what can be checked on the page:

- **"op woorden en betekenis"**: the passage is the closest in meaning and
  holds at least one query word; those words are marked;
- **"op betekenis"**: the passage is the closest in meaning and holds no query
  word; nothing is marked;
- **"op woorden"**: the search ran without an embedder (keyword search), so
  there is no question vector; the hit shows the fragment around the first
  query word, as before.

**Which words are marked.** The words of the question (`\w+`), matched
case-insensitively at a word start: "Vergunning" marks "vergunningen", while
"gunning" never marks the inside of "vergunningen". The whole word is marked.
Only words of **four characters or more** count, so "de" and "van" are neither
marked nor turn every reason into "both". That is a rule of thumb, not a
measurement. A pseudonym token (`[PERSOON:9f8e7d6c]`) is never marked or
counted, so the question "persoon" does not light up every token, and the
trimmed window never cuts a token in half. Marking is data, not markup: the template writes every piece of
the stored text through autoescape, so a `<script>` in a document arrives as
text.

**When today's fragment is shown instead.**

- A hit after the tenth (`size` comes from the URL): the fragment, no reason.
- A document of more than **200 passages** (about 30,000 words): its vectors
  are not read at all (`console_passage.MAX_PASSAGES`, counted from the stored
  text before the read), so one huge document cannot make the page heavy. The
  fragment, no reason.
- The number of stored passage vectors differs from the number of windows the
  stored text splits into (indexed under another passage size, or the text
  changed without a reindex), the document has no passage vectors, or its
  vectors have another dimension than the question's (indexed by another
  embedder; logged): the fragment, no reason.
- The index cannot be read for the passages, for whatever reason (unreachable,
  a 429 or 503 from OpenSearch, any other error), or the second embedding of
  the question fails after the same bounded retry `hybrid_search` uses: every
  hit shows the fragment and the page says "De passages zijn nu niet
  beschikbaar". The results themselves stay: the search succeeded. The log
  says which exception class, nothing more.
- A malformed stored vector (a `None` in it): that hit shows the fragment, the
  others keep their passage; one warning per page, with the count.

**The log line.** Every read logs one JSON line on the `wordsworth.search`
logger: `{"event": "passages_read", "driver": …, "ids": …, "passages": …,
"floats": …, "bytes": "unknown", "ms": …}`, with no id and no text. It is there
to measure the payload. `bytes` is "unknown" because the OpenSearch client
returns a parsed answer without its raw size; `floats` is the count of numbers
that crossed the wire, at roughly 20 bytes each as JSON. The **estimate** until
then: a passage vector is 1024 numbers (bge-m3), about 20 kB as JSON; a
12,000-word document has about 80 passages (1.6 MB), so ten of them are about
16 MB per page. The 200-passage cap bounds one document at about 4 MB. That is an estimate, not a measurement: the
OpenSearch read has run in CI on a small index only, and the figure from the
demo rehearsal on the real dossier replaces it here. If the read takes more
than a second there, the server-side alternative (a nested kNN with inner
hits) is reopened as a decision of its own.

The offered terms are examples, not a promise: whether one matches depends on the
corpus that happens to be loaded. A term with no hits says so; an index that is
down says *that*, rather than returning an empty list that reads as "nothing
matched".

A hit for a deleted or superseded document never shows, and the page offers no
toggle for it: deleting or superseding a document already removes its index
entry, so there is nothing a toggle could reveal. The rule here only guards
against a stale index entry that should not exist.

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

"Our own" means the `Origin`'s hostname and port equal the `Host` header's, with
a `Host` without a port taken to be on the default port of the `Origin`'s
scheme. Until 2026-09-24 it was a suffix match: a hostname that merely ended in
ours passed, and an `Origin` with a port — local development on
`localhost:8000` — was always refused.

A request with no `Origin` at all is allowed. curl, the CLI and the tests send
none, and locking them out would cost more than the hole. That is also the limit
of this defence: it stops a browser, not a script — and a browser is exactly what
the hole needed.

## Two deliveries at once

Ingesting into a dossier that does not exist yet creates it. Two requests doing
that at the same moment used to make one of them wait on the unique index for as
long as the other took — and in `/ingest` that transaction spans the whole
straat for a document — and then fail with a 500.

The insert now sits in a savepoint: if it collides, only that savepoint rolls
back and the loser reads what the winner just wrote. The savepoint is not there
to survive the collision but to save the rest of the session, which is carrying
half a document's work.

## What it deliberately cannot do

It reads the corpus through the same gate as `/documents/{id}/anonymized` and
`/export`: a caller that `WORDSWORTH_CORPUS_READ_LABELS` refuses there is refused
here. Until 2026-09-18 it was not, which made the console precisely the second
door its own docstring forbids.

### Een vraag stellen, niet een trefwoord typen

De zoekpagina embedt de **vraag zelf** en legt hem naast de lexicale treffers
(`hybrid_search`: RRF voor de kandidaten, cosinus voor de volgorde). Dat is wat
"stel een vraag" van "typ een trefwoord" onderscheidt — een vraag bevat zelden
de woorden die in het antwoord staan. *"Redenen tot afkeuring?"* vindt een stuk
waarin "afgewezen" staat; BM25 vindt daar niets.

Draait een instantie zonder embedder, dan blijft het BM25 **en zegt het scherm
dat**. Stil terugvallen op iets zwakkers is erger dan het niet hebben: dan wijt
een lezer de magere uitslag aan het corpus in plaats van aan de opstelling.

De dossiergrens en het onderwerp-filter gelden onverkort: een vraag stellen is
geen andere zoekopdracht, alleen een andere manier om er een te formuleren.

### Die lijst gaat over namen, en namen veranderen met de deur

`WORDSWORTH_CORPUS_READ_LABELS` bevat **callerlabels**, en wat een callerlabel
ís hangt af van hoe er ingelogd wordt:

| aanmelding | callerlabel |
| --- | --- |
| `WORDSWORTH_API_KEYS` | het label vóór de dubbele punt (`mark:sk_live_…` → `mark`) |
| Cloudflare Access | het **geverifieerde e-mailadres** uit het JWT |

Zet je de ene aanmelding om naar de andere, dan **verandert elk label** en
weigert de lijst iedereen. Dat gebeurde op 2026-09-19: de lijst stond nog op
`console` uit het sleuteltijdperk, terwijl de callers sinds de Access-uitrol
e-mailadressen waren. Gevolg: de hele console gaf 403 aan iedereen, ook aan de
beheerder.

Een 403 op een browserpad toont daarom nu een pagina die zegt ónder welke naam
je binnenkwam. Zonder dat weet niemand — de gebruiker niet en de beheerder niet
— welke naam er dan wél op de lijst moet. Welke namen er al op staan, zegt de
pagina bewust niet.

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
