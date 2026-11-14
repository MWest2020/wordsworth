# Design: api-corpus-read-gate

Closes #442. Code references are to origin/main `1dabaab`. "Measured" means
requested on the local demo (`tools/demo/serve_local.py --reset`, 2026-11-13)
with three callers: no key, `gast` (logged in, on no list) and `mark` (reader
and issuer).

## The rule

A route that returns corpus content or corpus metadata, or that changes what a
reader sees of the corpus, requires corpus read. Corpus metadata is anything
that says which documents exist, what state they are in, what they are about,
what PII types they carry or who was granted what on them.

The decision stays `auth.authorize_corpus_read(caller, labels)`, unchanged:

- list empty: the scope is off, every caller passes (as today);
- list set: only a listed label passes; no caller (auth off) is refused.

## The gate is a dependency, not a line in the body

New module `src/wordsworth/read_gate.py` (under 200 lines):

```python
class Gate:
    """A FastAPI dependency that raises 403, and names itself."""
    name: str                      # "corpus-read" | "grant-read" | "grant-admin"
    def __call__(self, request: Request) -> None: ...

def corpus_read(labels: list[str]) -> Gate: ...
def grant_read(labels, issuer_labels, auth_enabled) -> Gate: ...
def grant_admin(issuer_labels, auth_enabled) -> Gate: ...
def gate_of(route) -> str | None:  # the name of the gate a route declares
```

`create_app` builds the gates once, after the label lists are resolved, and
a route declares one: `@app.get("/search", dependencies=[Depends(may_read)])`.

Why a dependency:

- **It runs before the route body and before parameter validation.** A caller
  without corpus read gets 403 whether or not `q` is present and whether or not
  the id exists. Today `gast` gets 404 for an unknown document and 200 for a
  known one: an existence check for anyone with a key.
- **It is visible from outside the function.** `gate_of(route)` reads it from
  `route.dependant`, so a test can require it. A call in the body cannot be
  seen without running the route.
- **`api.py` does not grow.** It is 2009 lines against a limit of 200.
  `_guard_corpus_read` (five lines) leaves; the five body calls
  (`api.py:678, 711, 873, 1650` and `topic_labels_api.py:60`) become the same
  declaration; thirteen routes gain one argument. Net: not longer than today.

`grant_admin` is the decision `_guard_grant_admin` makes today
(`auth.authorize_grant_issue`), as a declarable gate. This change declares it
on one route, `POST /datasets/pseudonymize`. The ten routes that call
`_guard_grant_admin` in their body keep doing so.

One exception to "before validation": FastAPI reads and parses a JSON body
before it resolves dependencies, so a malformed JSON body on `POST
/documents/{id}/feedback`, `PATCH /topics/{id}` or `POST /reprocess` answers
422 to anyone. That says nothing about the corpus, and the spec says so. The
tests send a valid body.

The refusal is the one that exists: 403, `caller not authorized for corpus
read`. A browser gets the 403 page, as now.

The console keeps calling `_mag_lezen(request)` in its route bodies; that is
the same function underneath (`build_router` receives the gate). Moving 9
console routes to declarations is not needed to close the hole and is left
out. The two unguarded console routes get the body call the others have.

## Inventory

All 55 routes of an application with every optional backend mounted (walked
from `app.routes`, including the console router, which this FastAPI version
keeps nested). `any key` means: a valid key or identity, no further check.

### API: read

| Route | Today | New | Reason |
|---|---|---|---|
| `GET /documents/{id}/state` | any key (measured 200; 404 unknown) | corpus read | state and where a superseded copy went: which documents exist |
| `GET /documents/{id}` | any key (200) | corpus read | object key, source URL, PII counts, and every audit payload of the document, reveals and feedback with their callers included |
| `GET /documents/{id}/anonymized` | corpus read (`api.py:678`) | corpus read, declared | the text |
| `GET /documents/{id}/redacted.pdf` | corpus read (`:711`) | corpus read, declared; document read once #439 lands | the document |
| `GET /export/anonymized.zip` | corpus read (`:873`) | corpus read, declared | every text |
| `GET /search` | any key (200) | corpus read | ids, scores, object keys, matching passage |
| `GET /hybrid` | any key (200) | corpus read | same |
| `GET /ask` | any key (200) | corpus read | a generated answer over the passages, with citations |
| `GET /export/ranking.csv` | any key (200) | corpus read | rank, id, score, object key |
| `GET /dossiers/{id}/topics` | any key (200) | corpus read | what a dossier is about, document counts |
| `GET /grants/{id}` | any key (200; 404 unknown) | corpus read or grant issuer | recipient, types and document id of a grant; see below |

### API: writes that change what a reader sees

| Route | Today | New | Reason |
|---|---|---|---|
| `POST /documents/{id}/feedback` | any key (201, record written as `gast`; 404 unknown) | corpus read | writes on the document's audit chain; the console form for it is on a page behind corpus read |
| `POST /dossiers/{id}/topics` | any key (200, topics replaced) | corpus read | replaces every topic of the dossier and returns them; `POST /console/topics` is behind corpus read |
| `PATCH /topics/{id}` | any key (200, renamed) | corpus read | renames what every reader sees |
| `POST /topics/{id}/label` | corpus read (`topic_labels_api.py:60`) | corpus read, declared | |
| `POST /dossiers/{id}/summaries` | corpus read (`api.py:1650`) | corpus read, declared | |
| `POST /reprocess` | any key | corpus read | `problems` in the answer is keyed by document id with the error text, PII types included; a given id that does not exist is told apart from one that does; a call without a body re-de-identifies every indexed document (about 25 hours of GLiNER on the pilot corpus). Whether it deserves a narrower label than reading is #431's question; any key is not the answer meanwhile |

### API: other gates

| Route | Today | New | Reason |
|---|---|---|---|
| `GET /roles`, `POST /roles`, `PUT /roles/{name}/types`, `POST /roles/{name}/deactivate`, `POST /roles/{name}/activate` (5) | grant issuer (`_guard_grant_admin`) | same | roles decide what a grant reveals |
| `POST /grants`, `POST /grants/{id}/revoke` (2) | grant issuer | same | |
| `POST /datasets/pseudonymize` | any key (`api.py:1298`, no check) | **grant issuer**, declared | a token lookup; see "`POST /datasets/pseudonymize`" below |
| `DELETE /documents/{id}`, `DELETE /dossiers/{id}` (2) | `beheerder` or issuer (`_guard_delete`) | same | |
| `POST /documents/{id}/reveal`, `POST /documents/{id}/reveal.pdf` (2) | the grant: recipient, types, scope, expiry (`grants.authorize`) | same | a reveal is decided by its grant; adding corpus read would narrow a recipient who is no reader, which is what #439 is about |

### API: write path, undecided (#431)

| Route | Today | New | Reason |
|---|---|---|---|
| `POST /ingest` | any key | unchanged | issue #431 asks whether ingest needs its own label. Not decided here. What a non-reader can still do through it is listed under "Migration" |

### Console

| Route | Today | New | Reason |
|---|---|---|---|
| `GET /console`, `/console/dossier`, `/console/documents`, `/console/documents/{id}`, `/console/search`, `/console/topics`, `/console/feedback`; `POST /console/topics`, `/console/topics/{id}/label` (9) | corpus read (`_mag_lezen`; measured 403) | same | `/console/documents/{id}`: document read once #439 lands |
| `GET /console/combinations` | any key (`console.py:192`, no check; measured 200) | corpus read | lists every declared combination with the number of documents carrying it |
| `POST /console/combinations` | any key (`console.py:200`, no check; measured 303, stored) | corpus read | `session.merge` writes a declaration every reader sees on every document page, and replaces the reason and the name on an existing one |
| `GET /console/roles`, `POST /console/roles`, `POST /console/roles/switch` (3) | grant issuer (`_mag_beheren`) | same | |

### Open on purpose

| Route | Today | New | Why it stays |
|---|---|---|---|
| `GET /health` | no key | same | the three kubelet probes and oauth2-proxy's `--skip-auth-route` call it; it touches no backend and returns a constant |
| `GET /metrics` | no key, no rate limit | same | Prometheus text: documents per state, audit records per step, a failed count. No id, name, text or type, but more than size: see "Found and not changed". Exempt by the `api-key-auth` spec ("ops probes") |
| `GET /console/login`, `POST /console/login` | no key | same | nobody can bring a key to the page that asks for one; rate limited |
| `/console/static/*` | no key | same | the fonts, `fonts.css` and `console.js`: the console's own assets, needed by the login page. No corpus data; `console.js` is the script every console page loads |
| `GET /console/logout` | any key | same | clears the caller's own cookie |
| `GET /` | any key | same | a redirect to `/console`, or `{"detail": "see /docs"}` |
| `GET /openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` (4) | any key | same | describe the routes, not the corpus; a refused caller needs them to see what he is refused |

### Counts

| | API | Console | Total |
|---|---|---|---|
| Corpus read already | 5 | 9 | 14 |
| Corpus read, new | 12 | 2 | 14 |
| Grant issuer, new | 1 | 0 | 1 |
| Another gate, unchanged | 11 | 3 | 14 |
| Any key, undecided (#431) | 1 | 0 | 1 |
| Open on purpose | 7 | 4 | 11 |
| | 37 | 18 | 55 |

## `POST /datasets/pseudonymize`

The first version of this design left the route open and said it "touches no
document". That was wrong on both counts, and the security review of #446
caught it.

What the route does (`api.py:1298-1372`): it pseudonymises the cells of an
uploaded CSV with `Pseudonymizer(kp, PostgresMappingStore(session),
domain=prof.domain)`, the corpus's own keys and mapping store, in a domain the
caller names in the profile (default `_global`, the domain documents use). It
registers a document row for the upload, appends a `dataset_pseudonymize`
audit record and writes mapping rows. And it returns the tokens.

The same value in the same domain gets the same token in a dataset cell as in
a document; that is the feature (`datasets.py:4-8`). So for a caller who can
see tokens it is a lookup: upload a column of guessed names, read back their
tokens, compare with the tokens on the page. A share recipient sees raw tokens
on his document page and withheld types in a `/reveal` answer. With this route
open to any key, a grant at PPL 0 would let him confirm every name he can
guess.

Corpus read is not the right gate either. A reader sees every token in the
corpus and is not meant to resolve them; that takes a grant. Confirming a
guess is resolving. The callers who lose nothing by having the lookup are the
ones who can issue themselves a grant: the issuers. So the route goes behind
the grant-issue gate, in this change, and not behind #431.

Who calls it today: the thin client's `datasets` command, which sends no key
(#445). In production the issuer list and the read list are the same four
labels. Open to Mark, question 6.

## `GET /grants/{id}`

A grant is not corpus content, but it says which document was opened to whom
and for which types. Two kinds of caller have a reason to read one: an issuer
(he made it, and may revoke it) and a corpus reader (the console document page
shows him every active grant on a document already, `console_data.grants_for`).
So the gate `grant-read` admits either. In production the two lists are the
same four labels.

The recipient is not admitted by being the recipient. He receives the grant id
from the issuer and uses it on `/reveal`; inspecting it is not needed for
that. Open to Mark, question 1.

A caller who is neither gets 403 for a known and an unknown id.

## Composition with share-recipient-read (#439)

#439 adds `auth.authorize_document_read(caller, labels, shared=…)`: corpus
read, or a live document-scoped grant naming the caller. It applies it in two
places: the redacted PDF and the console document page.

**Order: #439 and #440 are deployed after this change; they can be built in
either order.** This change only narrows, depends on nothing, and is what
makes #439's sentence "the grant SHALL open nothing else" true of the API.

**How they fit.** When #439 is built on top of this change:

- its guard becomes a third gate in `read_gate.py`, `document-read`, declared
  on `GET /documents/{id}/redacted.pdf` in place of `corpus-read`. It opens its
  own short session to resolve `shared`, and keeps #439's rule that every
  refusal is the same 403 before any lookup;
- `/console/documents/{id}` calls the same decision from its body, as #439
  describes;
- the inventory test's row for those two routes changes from `corpus-read` to
  `document-read`, in #439's own diff. That is the only place the two changes
  touch the same lines, and #439's tasks.md needs one line for it.

**Which routes take document read: the two #439 names, and no more.** Of the
single-document routes gated here:

| Route | Document read? | Why |
|---|---|---|
| `GET /documents/{id}/anonymized` | no | #439 keeps it closed on purpose |
| `GET /documents/{id}` | no | returns every audit payload of the document: who revealed, who gave feedback. #439 hides exactly that from a recipient |
| `POST /documents/{id}/feedback` | no | #439 leaves the feedback form off the recipient's page |
| `GET /documents/{id}/state` | no, by default | shows nothing the recipient's page does not show, but no flow needs it. Open to Mark, question 2 |

If #439 is built first instead, nothing breaks: this change then moves
`_guard_document_read` into `read_gate.py` as it moves `_guard_corpus_read`,
and writes the rows below itself.

**Rows that arrive with the sharing changes.** Whichever is built second adds
them to `tests/route_inventory.py`; #439's and #440's tasks.md each need a
line for it, which this change does not write on their branches.

| Route | From | Policy | Reason |
|---|---|---|---|
| `GET /documents/{id}/redacted.pdf` | #439 | `document-read` (was `corpus-read`) | corpus read, or a live share on this document |
| `GET /console/documents/{id}` | #439 | `document-read` (was `corpus-read`) | same decision, narrower page |
| `GET /console/gedeeld` | #439 | `own-shares` | any key; lists the caller's own live shares and nothing else. The refusal test asserts that a caller on no list gets 200 and an empty list, and that another caller's share is absent |
| `GET /console/share`, `POST /console/share`, `GET /console/shares`, `GET /console/shares/{share_id}`, `POST /console/shares/{share_id}/revoke` (5) | #440 | `grant-admin` | sharing is issuing; exactly `authorize_grant_issue` |

`document-read` and `own-shares` are the two policies the sharing changes add
to the seven below. A row with `document-read` is requested twice by the
refusal test: as a caller on no list (403) and as a recipient (200).

**Deploy preconditions for #439 and #440**, checked in their deploy PRs:

1. this change is in production (task 6.3 done);
2. `WORDSWORTH_CORPUS_READ_LABELS` is not empty. An empty list means the scope
   is off: every caller reads everything, and a share then restricts nothing.
   See "An empty read list".

## The test that keeps the inventory true

`tests/route_inventory.py` holds the inventory as data: one row per method and
path with a policy (`corpus-read`, `grant-read`, `grant-admin`, `delete`,
`grant`, `any-key`, `open`) and a reason. The tests are in
`tests/test_route_inventory.py`. Each file stays under 200 lines; if the rows
outgrow that, the API rows and the console rows become two data files.

1. **Walk.** Build the application with every optional backend, collect its
   routes, and require: every route has a row, every row has a route, and
   every API row with policy `corpus-read`, `grant-read` or a declared
   `grant-admin` declares that gate (`read_gate.gate_of`). The walk is only as
   good as its reach, so it is closed on four sides:
   - **Every conditional route is mounted.** The test reads
     `inspect.signature(create_app)` and fails unless each parameter is either
     passed by the fixture or named, with a reason, in a short list of
     parameters that mount no route. A new optional backend that the fixture
     does not pass fails here, before its routes can go unseen. As a second
     count, the route decorators and `app.mount` calls found in `src/` must
     equal the inventory rows minus the four the framework adds.
   - **Every container is opened.** The collector descends into every included
     router (`_IncludedRouter.original_router.routes`, which is where this
     FastAPI version keeps the console) and into every `Mount`, recursively. A
     mount of static files is one row; a mount of an application is walked.
   - **Nothing unknown passes.** The collector knows `APIRoute`, Starlette
     `Route`, `Mount` and the included router. Any other object in a route
     list fails the test and names its type.
   - **No WebSocket.** `ApiKeyAuthMiddleware` passes every non-HTTP scope
     through unauthenticated (`auth.py`: `scope["type"] != "http"`), so a
     `WebSocketRoute` would be reachable without a key. The test fails on one;
     a change that needs one has to bring its own authentication and change
     this test knowingly.
   - **HEAD.** Rows are keyed by method and path. `HEAD` is folded into the
     `GET` row of the same route object when that object answers both (the
     framework's four schema routes do); it gets the same policy and the
     refusal test requests it too. A route answering `HEAD` without `GET`
     needs its own row. `OPTIONS` is answered by the CORS middleware before
     any route and is not a row.
2. **Refusal.** For every row, request it as a logged-in caller on no list,
   with valid parameters and an existing id, and require the status the policy
   promises: 403 for `corpus-read`, `grant-read`, `grant-admin` and `delete`;
   not 401 and not 403 for `any-key` and `open`. This covers the rows whose
   check is in the body.
3. **Nothing happened.** For the gated writes, the refused request left no
   trace: no audit record, no document row, no mapping row, no topic change,
   no declared combination.

The walk catches a forgotten route at once; the refusal test catches a gate
that is declared and does not refuse.

## An empty read list

`authorize_corpus_read` passes every caller when the list is empty. That is
the documented default and this change keeps it: an installation inside a
trusted boundary sets no list. But it fails open. In production the door is
oauth2-proxy with `--email-domain=*`; if the ConfigMap line is lost, every
account in the realm reads the corpus, and every route of this change answers
200 again without one test going red.

Two things are added, and neither changes an answer:

- **A startup warning.** When caller authentication is on, a grant store is
  configured and the read list is empty, `create_app` logs one structured
  warning: the scope is off and every authenticated caller reads the corpus.
  Authentication plus grants means somebody is deciding who sees what; an
  empty list there is more likely forgotten than chosen. It is a warning and
  not a refusal to start, because the configuration is legal.
- **A deploy precondition** for #439 and #440 (above) and for this change's
  own rollout (task 6.1).

## Who is the caller: `email_verified`

A caller under the identity provider is the `email` claim of a verified token
(`access_identity.email_from`). The read list and the grants name callers by
that address. `email_from` checks signature, algorithm, audience, issuer and
expiry, and does not look at `email_verified`. So the question "who is on the
list" is only as strong as the realm's answer to "who may put this address in
a token": with self-registration, or with users editing their own address, an
account could carry `mark@westerweel.work` unverified and be a reader and an
issuer. A bearer token is also accepted on the tailnet path, which does not
pass oauth2-proxy.

Closing the read gate while leaving that open would be measuring the lock and
not the door. So, in this change:

- The OIDC verifier (`WORDSWORTH_OIDC_*`) refuses a token whose
  `email_verified` is not literally `true`; an absent claim is a refusal.
- A Cloudflare Access assertion (`WORDSWORTH_ACCESS_*`) carries no such claim
  and is unchanged: Access itself establishes the address. The spec keeps
  Access as one possible provider.
- A refused token yields no caller, as every other refusal in `email_from`
  does; a key still works.
- Deploy task 6.1 also reads, and reports without changing, the realm's
  settings for self-registration, editing one's own address and verify-email,
  and that the two listed addresses are verified. Otherwise this could lock
  Mark out of the console behind Keycloak (the `console` key remains).

## Migration: who calls these routes without being a reader

Production (`MWest2020/homelab`, `cluster-config/infra/wordsworth/`, and
`kubectl -n wordsworth get` on names and the ConfigMap, 2026-11-13):
`WORDSWORTH_CORPUS_READ_LABELS` and `WORDSWORTH_GRANT_ISSUER_LABELS` are both
`console,cli,mark@westerweel.work,markwesterweel@gmail.com`. Auth is on: the
API mounts the Secret `wordsworth-apikeys` and an OIDC verifier (Keycloak,
realm `westerweel`, through oauth2-proxy with `--email-domain=*`).

| Caller | Routes it uses | Label | After this change |
|---|---|---|---|
| A person through Keycloak, on the list (two addresses) | console, API | the verified address | unchanged |
| **A person through Keycloak, not on the list** | any | the address in the token | **403 on the 15 routes.** Every account in the realm passes oauth2-proxy and becomes a caller. This is the hole, closing. How many such accounts exist was not looked up |
| **A key in `wordsworth-apikeys` whose label is not `console` or `cli`** | any | unknown | **403 on the 15 routes.** The Secret's labels were not read (they sit in the value next to the keys). The homelab docs name `console` and `cli` only; `docs/how-to/api-auth.md` uses `acceptance` and `mark` as examples. Rollout task 6.1 prints the labels, and only the labels, before the deploy |
| Thin client (`wordsworth`, `wordsworthctl`; `client.py`) | search, hybrid, ask, state, show, export, grants, datasets, reprocess, ingest | **none** | **unchanged, because it is already refused.** `client.py` sends no `X-API-Key` and has no flag, variable or config entry for one. By the code every command except `health` answers 401 against production today (not measured against production). The gate cannot break it; it needs its own fix, issue #445 |
| `wordsworth-console` on GitHub Pages (browser, CORS) | the API | the key the operator pastes | unchanged with a `console` or `cli` key |
| NiFi | `POST /ingest` (ADR-0001) | | not deployed: no namespace, no manifest; `/ingest` is not gated here |
| Nextcloud connector | `POST /ingest` only | `WORDSWORTH_API_KEY` | unchanged |
| `deploy/k8s/45-reprocess-job.yaml` | `POST /reprocess` | `console` when the Secret has it, otherwise the first key | unchanged with `console`, which is on the read list. The fallback to "the first key" would now be refused where that label is no reader: the template says so after this change |
| A person through Keycloak whose token has no `email_verified: true` | any | none | no caller: 401, or the login page. Checked for the two listed addresses in task 6.1 |
| `wordsworth-ingest` Job, `ww-*` Jobs, backup and renew CronJobs | none: database and object store directly | | unchanged |
| Probes | `/health` | none | unchanged |
| Local demo, caller `gast` | any | `gast` | 403 on the 15 routes: `docs/how-to/local-demo.md` and the demo script change with it |

A caller that uploads and then polls `GET /documents/{id}/state` with a key
that is no reader would be refused. None exists in the deployment or the docs:
`/ingest` answers synchronously with each file's state. If #431 introduces an
ingest-only label, this is where the two meet.

An installation with an empty read list keeps every answer it has; with
authentication and grants on, it gets the startup warning. An installation
with an issuer list keeps `POST /datasets/pseudonymize` for its issuers only.

**What a caller who is no reader can still do, through `POST /ingest`**
(deferred to #431, and the reason #431 should not wait long once such callers
exist):

- create documents, and create a dossier under any name;
- put a document into an **existing** dossier by naming it, so that readers
  find it there and in their search results;
- learn whether given bytes are already in the corpus: the answer is
  `skipped` or `added_to_dossier` for a known file and `indexed` for a new one;
- choose the pseudonymisation domain and the recorded provenance
  (`source_url`, `fetched_at`) of what he uploads;
- read back, for his own upload, the document id, the state and the PII
  counts per type;
- spend GLiNER, OCR and embedding time.

He cannot read anything back afterwards: state, metadata, text and search are
behind corpus read.

## Found and not changed

- **`/metrics` needs no key**, by the `api-key-auth` spec, and it is exempt
  from rate limiting as well (`rate_limit.EXEMPT_PATHS`). It gives more than
  the corpus size: `wordsworth_transitions_total{step=…}` counts audit records
  per step, so it tells anyone who can reach the Service how many reveals
  (`deanonymize`), deletions, feedback reports and `dataset_pseudonymize` runs
  there have been, and polling it shows when one happens. Each request runs a
  `DISTINCT ON (document_id)` over the whole audit table (`metrics.py:17-20`),
  unauthenticated and unlimited. No scraper was found in the cluster config
  (no ServiceMonitor or PodMonitor names wordsworth). The public tunnel's
  ingress rule is managed at Cloudflare and not in Git, so whether `/metrics`
  is reachable from outside could not be read here. Open to Mark, question 3.
- **A reader can overwrite another reader's declared combination**
  (`session.merge` on the type set). After this change only readers can; who
  may is a separate question.
- **`/ask` and `/export/ranking.csv` take no dossier scope**, unlike
  `/search` and `/hybrid`.
- **The thin client cannot authenticate** (above; issue #445).
- **`docs/how-to/api-auth.md`** lists `/ingest/nextcloud`, a route that does
  not exist, and says "enabling it does not change any other behaviour"; it is
  corrected in this change's docs task.

## Open to Mark

Working assumptions, each overrulable. The build goes ahead on the defaults.

1. **`GET /grants/{id}`: a corpus reader or an issuer may read a grant; its
   recipient, as such, may not.** Alternative: the recipient may read his own.
2. **A share recipient does not get `GET /documents/{id}/state`** when #439
   lands; document read stays on #439's two routes.
3. **`/metrics` stays without a key and without a rate limit**, although it
   shows per-step audit counts (reveals, deletions, feedback, dataset runs)
   and costs a scan of the audit table per request. Alternative: behind a key,
   with a scraper key, or the per-step counter left out for a caller without
   one.
4. **Before the deploy the build session prints the labels in
   `wordsworth-apikeys`, never the keys**, and reports any label that is not
   on the read list. It adds none to the list.
5. **#439 and #440 are deployed after this change** (built in either order),
   and only with a read list that is not empty.
6. **`POST /datasets/pseudonymize` is for grant issuers.** Alternative: its
   own label, decided with #431.
7. **An OIDC token without `email_verified: true` names no caller.**
   Alternative: leave the code and make the realm settings a deploy check
   only.
