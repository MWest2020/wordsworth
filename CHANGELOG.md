# Changelog

## [Unreleased]

### Security

- **`reveal` and `reveal.pdf` told an uncovered caller whether a document
  exists, is deleted, or which copy survives it** (#487, found by the
  security review of #485). Both routes now decide the grant
  (`grants.authorize()`, recipient, revocation, expiry, domain and scope)
  before reading anything about the document; a caller the grant does not
  cover gets one answer whatever the cause — 403 `{"detail": "grant not
  applicable"}` — for an unknown grant, a revoked or expired one, one scoped
  elsewhere, an unknown document, a superseded one and a deleted one alike.
  Only a caller the grant covers still hears 410 (deleted) or 409 (superseded,
  naming the survivor). A refusal writes no audit record and logs nothing
  about its cause. This closes the last existence oracle on a corpus-read
  route and clears the way for `share-recipient-read` (#439) and
  `console-share` (#440), which hand a grant id to callers who are not
  readers.

### Fixed

- **The seal run left a scan retired as a copy in plaintext, and a rerun
  downloaded every sealed object** (#486, #491). When OCR recovery finds the
  OCR'd PDF is already another document's object, it retires the scan's
  document as a copy (`supersede` with `as_object`); that document keeps its
  own object, the scan, and no `ocr` record names it, so the seal run never
  saw it and `--verify` passed over it. It is now a candidate of kind `scan`
  (counted under `scans`, `gone` when the store no longer has it), re-checked
  under the row lock so a deleted document stays deleted. A rerun now reads
  only the 30-byte header of an object whose key row has `sealed_at` and
  whose header is sealed, and reports it `already_sealed`; anything else
  still takes the full read. Spec: `openspec/specs/original-encryption`.

- **Concurrency fixes around deletion** (#460, #465, #466, #469, #504); the
  one lock order is now written down in `docs/reference/lock-order.md`.
  - A deletion could remove a `pii_mappings` row that another document, being
    anonymised at that moment, was about to rely on; that document's token
    could then never be revealed (#465). Mappings are now stored, linked and
    removed under the audit chain lock only: `PostgresMappingStore.put`
    buffers, and the rows are written in pseudonym order once the lock is
    held (at the link, or before a dataset run's record). Nothing writes
    them implicitly: a commit with rows still buffered is refused with
    `UnwrittenMappings`, and a savepoint neither writes nor drops them. The
    pseudonym backfill links the same way, one transaction per document,
    under the document's row lock.
  - That also ends the deadlock between two runs minting the same new value
    (#504): no mapping row is held before the chain lock any more.
  - The API's already-indexed ingest path added a dossier membership without
    locking the document; a dossier deletion in flight still deleted it,
    leaving a deleted document as a member (#466). It now locks the row and
    checks again (`ingest_existing.py`); bytes whose document was deleted
    meanwhile are ingested as a new document, and a deleted document still
    holding its key is refused with the text naming
    `wordsworth-release-deleted-keys`.
  - `wordsworth-release-deleted-keys` and `wordsworth-dedupe` took the audit
    chain lock before a document row and could deadlock with a deletion or
    an ingest (#466). Both lock the rows first; `audit.lock_chain` flushes
    pending row changes before it locks.
  - `reprocess` counted a document deleted mid-run as `reanonymized` (#469);
    it is now `skipped`, with a `reprocess_skipped` log line naming the state
    found. `problems` stays failures only.
  - The dossier-deletion lock-order inversion (#460) was fixed with #462;
    this adds the test the issue asked for.

- **The labels on a redacted PDF's boxes could not be seen** (#448). The
  invisible text layer left the PDF text render mode at 3, and the labels
  drawn after it inherited it: `[PERSOON 1]` was in the file and findable,
  and invisible on every box. The layer now sets the mode back. A label also
  shrinks to the width of its box and is clipped to it, so none runs out in
  white over the page. `RENDER_VERSION` is 2: redacted PDFs cached under
  version 1 are rendered anew on their next request.

- **`wordsworth ingest` reported every file as failed when the API answered
  503** (#403). A 503 is the server, not the files: the client still retries
  the batch (honouring `Retry-After`), and when the last attempt is a 503 it
  stops the run, counts what that 503 reported as finished, and lists the
  rest as `NOT INGESTED (server busy)` instead of `FAILED`. Other 5xx
  answers are handled as before.

- **A deletion racing `reanonymize` put the document back in the index**
  (#463). `reanonymize` (the `reprocess` backfill) read the state without a
  lock; a deletion that committed before it wrote the index entry and the
  text saw both come back, with a `reanonymize` record after `deleted`. It
  now locks the document row `FOR SHARE` before it reads the state, as
  `process` does (#462): a deletion waits and then removes what it wrote, and
  a `reanonymize` that finds a deletion under way waits and then skips it.

- **A deletion during processing left the document's text in the index**
  (#462). A deletion that started while `process` ran found no index entry
  yet, waited for the audit chain lock, and recorded `deleted` after
  `process` had indexed the document and stored its anonymized text; both
  stayed. `process` now locks the document row `FOR SHARE` before it reads
  the state, so the deletion waits and then removes the index entry and the
  text, and a `process` that finds a deletion under way waits and then does
  nothing. A dossier deletion locks all its members' rows, and those of
  their superseded copies, before its first audit record: otherwise it
  deadlocked with a `process` or an `ingest` (#452) of a member it had not
  reached yet (and, with crypto-shred, with a deletion of such a copy).

- **An ingest racing a deletion could bring the deleted original back**
  (#452). `ingest` now locks the live document's row `FOR SHARE` after
  `register_live` and re-checks it before `write_original`; a document deleted
  (or superseded) in between is looked up again, so the bytes become a new
  document and the deleted one gets no write and no key row. A deletion now
  locks the document row (`FOR NO KEY UPDATE`) before it removes anything,
  so an ingest cannot write the object back mid-deletion either (a dry run
  takes no lock); a supersession (OCR recovery retiring a scan, `dedupe`)
  locks the copy's row before its first audit record, the order an ingest
  uses, so the two no longer deadlock. A deleted document that still holds
  its content key is refused instead of written again: `POST /ingest`
  reports that file as `error` with a fixed text pointing at
  `wordsworth-release-deleted-keys`, `wordsworth-ingest` prints it and goes
  on, and the server log gets one `ingest_refused` line (document id and
  object key, never the filename).

- **A deleted document kept its summary** (#455). Deletion now removes its
  `document_summaries` row (LLM text derived from the document), counted as
  `summaries_removed` in the `deleted` record, the API answer and the CLI
  output; a dry run counts it. A rerun of `wordsworth-delete` over a document
  deleted earlier removes a leftover summary and records it on the same
  `remove-renders` record as the renders. `samenvatten --ontbrekend` skips
  documents without stored text (a deleted document no longer makes the
  CronJob exit 1), and a summary is stored only while the document's text is
  still there.

- **A deleted document's redacted PDF was still served** (#451). Deletion now
  removes its cached renders (`redacted/<doc>/`) and its `box_maps` row,
  counted as `renders_removed` and `box_maps_removed`;
  `GET .../redacted.pdf` and `POST .../reveal.pdf` answer 410 for a deleted
  document before looking at the cache. A rerun of `wordsworth-delete` over a
  document deleted earlier removes what it left behind (`remove-renders`).

- **A redacted PDF hid nothing on real documents.** pdfium reported a tight
  character box 0.01 pt high for every character of the Word-exported Gooise
  Meren Woo PDFs, so every redaction box had zero height and the page raster
  kept every name. `pdf_text.char_box` now falls back to the loose box when
  the tight one is degenerate (text, box map and render all use it), the
  render refuses a box without surface, and both PDF endpoints answer 409
  until the box map is rebuilt. The two cached renders were deleted.

### Added

- **Web addresses are detected** (`urls-are-detected`, issue #124). A
  `deny.json` rule turns every `http(s)://` or `www.` address into a `URL`
  token, and `allow.json` lists the public hosts it leaves alone, each with a
  reason: the municipality (and the OCR-garbled spellings of its own domain),
  regional and national government, public registers. Before this, nothing in
  the chain detected a URL, and `www.eazwind.nl` survived two lines below
  `info@eazwind.nl`, which did not. Measured on the evaluation corpus: URL
  recall 0 → 1.0 (145 of 145), zero false positives on 123 government
  addresses. See [meting 06](docs/explanation/meting-webadressen-06.md).
  **Behaviour change in the lists:** an allow rule now also removes what a
  deny rule of the same type added. Before, deny appended after the allow
  filter, so no exception could be written for a deny rule. Allow still never
  crosses types; on the evaluation corpus none of the 207 street-address
  matches is affected.
- `python -m wordsworth.samenvatten`: samenvatten is nu een echt commando
  (`--dossier <uuid>`, herhaalbaar, of `--ontbrekend` voor alles wat nog geen
  samenvatting heeft), niet langer een script dat een cluster-Job meedroeg in
  zijn eigen `args`. Idempotent zoals `compute()` dat al was, met één regel
  uitvoer (de vijf tellingen plus de duur) en een exitcode ongelijk aan nul
  als er iets mislukte. Zie [samenvattingen](docs/how-to/samenvattingen.md).
- Identity from Keycloak (or any OIDC issuer), alongside Cloudflare Access.
  `access_identity.Verifier` now holds issuer, audience and JWKS address as
  plain fields; `Verifier.cloudflare(...)` and `Verifier.oidc(...)` are two
  ways to build the same verifier, not two code paths. The JWKS address for
  an OIDC issuer is resolved from its `.well-known/openid-configuration`
  document and cached. Configure via `WORDSWORTH_OIDC_ISSUER` and
  `WORDSWORTH_OIDC_AUDIENCE`; existing `WORDSWORTH_ACCESS_TEAM_DOMAIN` /
  `WORDSWORTH_ACCESS_AUD` configuration keeps working unchanged.
- The token may now also arrive as `Authorization: Bearer …` (what a reverse
  proxy such as oauth2-proxy sends), alongside the existing
  `cf-access-jwt-assertion` header. The readable
  `cf-access-authenticated-user-email` header is still never trusted.
- `WORDSWORTH_OIDC_JWKS_URL` sets the JWKS address directly, skipping OIDC
  discovery — for fetching an issuer's keys from a neighbour in the same
  cluster instead of round-tripping through the public internet. The issuer
  stays the configured public name either way, since that is what is checked
  against `iss`.

### Fixed

- OIDC discovery no longer runs at startup. An unreachable or slow issuer used
  to crash the worker before it could boot, taking down routes that have
  nothing to do with logging in; the fetch now happens on the first request
  that verifies a token, with the result cached, and a failure there yields no
  caller instead of a dead process. Every discovery/JWKS request now also
  sends a `User-Agent`: Cloudflare was answering the bare `urllib` one with a
  403 while `curl` from the same pod got a 200.
