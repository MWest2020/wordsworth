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

Then open `/console/login` and enter the key. It is stored in an HttpOnly,
SameSite=strict cookie for eight hours.

The cookie is a second **transport** for the key, not a second check: the same
middleware, the same key set, the same caller label. A browser cannot set
`X-API-Key` on a plain navigation, and putting the key in a query string would
leak it into logs, history and referrers.

`/console/login` is exempt from authentication — you cannot bring a key to the
page that asks for one — and stays subject to rate limiting, because that is the
one route where guessing pays.

## What the pages show

**`/console`** lists documents with their state and the PII types found, most
recently touched first. The types come from the pseudonyms the pipeline *minted*
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

## What it deliberately cannot do

It never reveals. Re-identification has exactly one door: the grant-gated,
audited `reveal` endpoint (see [grants](grants.md)). An inspection screen that
may also reveal is a second door with a friendlier name, and it is the one
nobody audits.

It does not edit documents. Reading, and recording a combination.

## A caveat worth seeing on screen

If the deployment runs without the GLiNER/OpenAnonymiser layer, names stay in
the clear in the stored text — and the console shows them, because it shows what
the pipeline actually produced. That is the same finding as the `PERSON` leaks
in [the evaluation](../reference/evaluation.md): a property of that deployment,
not of the screen.
