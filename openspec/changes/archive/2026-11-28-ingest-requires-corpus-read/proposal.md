# ingest-requires-corpus-read

## Why

Issue #526, found by the weekly self-scan (homelab `tools/security-report`,
layer 2) with a test user in realm `westerweel` who has no group, no role and
no address on either label list. `POST /ingest` declares no gate and checks no
caller, so authentication alone is enough. Behind oauth2-proxy that means every
account in the realm, not the label lists.

What such a caller can do through it was listed in #431: create documents and
dossiers, put a document into an existing dossier that readers search and that
`/ask` answers from, add an existing document to another dossier, learn whether
given bytes are in the corpus, choose the pseudonymisation domain and the
recorded provenance, and spend OCR, NER, embedding and key-service time. An
upload also writes into sealed storage that cannot simply be cleaned up. No
confidentiality impact was found: the same caller gets 403 on every read and
reveal route.

#431 asked whether ingest should need a label; the default ("no change") was
taken on 18 Nov. The self-scan now shows the open route is reachable by every
realm account, which #431 had not checked. This change takes the smallest step
that closes it, and leaves the dedicated list #431 recommended open (see
"Open question").

## What changes

- `POST /ingest` requires corpus read: the same declared gate (`corpus_read`,
  `WORDSWORTH_CORPUS_READ_LABELS`) the other writes that change what readers
  see already require (`POST /reprocess`, feedback, topics, summaries).
- The refusal comes before the upload is read. A declared gate runs before
  validation but after FastAPI has parsed a multipart body; a new route class,
  `read_gate.GateFirst`, runs the route's declared gates first. Only
  `POST /ingest` uses it.
- The route inventory records `POST /ingest` as corpus read, and a new check
  fails the suite when a writing route is recorded as any-key or open, except
  the console's login form. The next write route cannot ship ungated with a
  row nobody looked at.

## What does not change

- Production callers: the thin client (`cli`) and the console (`console`) are
  on the read list in `cluster-config/infra/wordsworth/configmap.yaml`, as are
  Mark's two addresses. The `wordsworth-ingest` Job writes to the database
  directly and is no caller. NiFi and the Nextcloud connector are not deployed.
- With the read list empty the scope is off: any key still ingests. Without
  authentication nothing changes.
- A missing or invalid key is still 401.
- The other routes keep the gates they have; nothing else moves to
  `GateFirst`. In particular the JSON routes keep answering a malformed body
  422 before the gate, as "A corpus-read refusal comes before the lookup"
  allows.

## Open question

Corpus read or its own list. #431 recommended a dedicated
`WORDSWORTH_INGEST_LABELS`, so that a connector that only delivers files does
not also read the corpus, and a reader does not also write into dossiers other
readers search. This change reuses the read list because that is the right the
existing corpus writes already require, and because production has no caller
today that should ingest without reading. A dedicated list can follow as its
own change without undoing this one.

## Out of scope

The caller in the `register` audit record (#431, point 4); converting the
body-called grant-admin checks to declared gates; a dossier as a write
boundary.
