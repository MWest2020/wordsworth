# Design

Both routes sit behind the skeleton's service token (401 first). Request
logging drops the body and the response: no original byte or key byte reaches
a log. This change's tests run under the fixture that makes `config.settings`
raise.

## The document-key store is the service's own

`doc_keys.py` (≤ 200 lines) reimplements `mint`, `unwrap`, `evict` and the
bounded unwrap cache of wordsworth's `DocumentKeys` over the service's own
`DocumentKeyRecord` (`keyservice/models.py`), with the cache size and TTL as
plain constructor arguments taken from `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE`
and `KEYSERVICE_KEY_CACHE_TTL`. Its KEK name comes from `kek_for(domain)`:
`KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN.get(domain, KEYSERVICE_ORIGINALS_KEK)`.

Decided: reimplement. wordsworth's `DocumentKeys` inserts and selects
wordsworth's `DocumentKeyRecord` (`models.Base`); because the service copied
the table's name and columns it would silently work against the service's
session, which is exactly the case skeleton rule 3 forbids. Rejected: making
`DocumentKeys` model-agnostic with a record-class argument (a wordsworth edit
whose only gain is about 100 shared lines, and a second consumer of a class
whose cache semantics are wordsworth's); parameterising
`document_keys.kek_name_for` (a wordsworth edit for a one-line lookup). The
two stores agree on the bytes because both use `originals_envelope` and the
same wrap; the cutover's "every original opens" verification is what proves
it on real data.

`unwrap` classifies a failure, which wordsworth's collapses into one
`OriginalsKeyUnavailable`:

- `KeyBackendUnavailable`: the Transit call did not get an answer about the
  ciphertext: a connect or timeout error, or an HTTP 5xx (OpenBao sealed or
  down) from `OpenBaoTransit`.
- `KeyDoesNotUnwrap`: the backend answered and refused the ciphertext: an
  HTTP 4xx from `OpenBaoTransit`, `cryptography`'s `InvalidTag` from
  `FakeTransit`.

Anything else propagates as a 500. Rejected: inferring the cause from the
message text.

## Settings

| Setting | Default | Note |
|---|---|---|
| `KEYSERVICE_ORIGINALS_KEK` | the value of `KEYSERVICE_TRANSIT_KEK` | as wordsworth's `originals_kek` defaults to its `transit_kek_name` |
| `KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN` | empty | `domain:kek` pairs |
| `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE` | 1 024 | |
| `KEYSERVICE_MAX_ORIGINAL_BYTES` | 104 857 600 (100 MiB) | seal and open both hold the whole body in memory up to this bound; 413 beyond |

## `POST /v1/originals/{document_id}/seal`

Request: the original's bytes as `application/octet-stream`; query `domain`
and `object_key`.

`put_original`'s five rules are decided from the bytes already in the object
store, which the service never sees, so "the same semantics minus the
object-store write" is not definable. These are the rules that hold without
an object store:

1. **First seal of an object key.** Mint a data key wrapped under
   `kek_for(domain)`, insert the row (`document_id` = this document), seal
   the bytes with `originals_envelope.seal`, set `sealed_at`, return the
   sealed bytes with `X-Key-Id`.
2. **A second seal of the same object key for the same document.** Unwrap the
   row's key and seal under it: never a second data key for one object key,
   or a copy stored earlier opens under no key. Same `X-Key-Id`; `sealed_at`
   is set again. `mint` adopting the winner on a concurrent insert is the same
   rule under a race.
3. **An object key whose row belongs to another document.** 409 `{"detail":
   "object key belongs to another document"}`, nothing written. Rejected:
   re-pointing the row as `put_original` does on a re-ingest; that is why
   wordsworth's `deletion_keys` says a row's `document_id` is not a reliable
   owner, and in the service it must be one, because `open` and the
   deletions are scoped by it.

`sealed_at` is set when the sealed bytes are returned. The service cannot
know whether wordsworth then stored them; if that write fails, wordsworth's
next attempt is a reseal (rule 2), never a second key. Rejected: leaving it
NULL, which keeps a column nothing ever sets and leaves the cutover nothing to
copy into wordsworth's downgrade guard.

`put_original`'s rules 1 (unchanged bytes), 4 (legacy plaintext) and 5 (the
downgrade guard) are decided from the stored object and stay wordsworth's;
how they read the key id after the switch is `key-service-cutover`'s
question, which this change does not answer.

`known_documents` is checked through `known.py` exactly as `pseudonymise`
does (409 other domain, 410 tombstoned, else record it), under lock 1 then
the row, then the `document_keys` row `FOR UPDATE` (the lock order of
`key-service-pseudonymise`).

| Case | Status |
|---|---|
| no or unknown service token | 401 |
| body over `KEYSERVICE_MAX_ORIGINAL_BYTES` | 413 |
| `domain` or `object_key` missing, `domain` empty or containing `/` | 422 |
| document known in another domain | 409 `{"detail": "document is registered in another domain"}` |
| object key's row belongs to another document | 409 `{"detail": "object key belongs to another document"}` |
| document tombstoned | 410 `{"detail": "document deleted"}` |
| Transit unreachable or sealed | 503 `{"detail": "key service unavailable"}`, nothing committed |
| otherwise | 200, sealed bytes, `X-Key-Id` |

Audit: `event = "seal"`, document, `object_key`, key id, and whether a key
was minted or reused.

## `POST /v1/originals/{document_id}/open`

Request: the sealed bytes as `application/octet-stream`; query `object_key`
and `purpose`. The purpose is one of `process`, `reanonymize`,
`ocr_recovery`, `redacted_pdf`, `reveal_pdf`, `seal_verify` (the readers of
`docs/reference/originals-readers.md` plus verification).

| Case | Status | Audit |
|---|---|---|
| no or unknown service token | 401 | none |
| purpose missing or not in the list; malformed query | 422 | none |
| body over `KEYSERVICE_MAX_ORIGINAL_BYTES` | 413 | none |
| no key row for `object_key` with this `document_id` | 404 `{"detail": "no key for this object"}` | `open_refused`, `reason = "no_key"` |
| `KeyBackendUnavailable` | 503 `{"detail": "key service unavailable"}` | none (nothing was decided) |
| `KeyDoesNotUnwrap`, or the envelope does not authenticate | 409 `{"detail": "sealed object does not open"}` | `open_failed`, `reason = "unwrap"` or `"envelope"` |
| otherwise | 200, the plaintext | `open`, document, `object_key`, purpose |

"With this `document_id`" is well defined because seal never re-points a row
(rule 3). A 404 is no oracle: only a calling service with a token reaches the
route, and it is the one that stored the object. `key-service-open-limits`
puts the rate limit between the 422 and the 404, inside the route, so the
order 401, 422, 429 holds.

## The wire

`open` returns the original in plaintext over HTTP on the link between
wordsworth and the service, and `seal` receives it the same way. Whoever can
read that link reads the originals in transit; encryption at rest does not
cover it. The link is a transport the deployment chooses (ADR-0009 names
mutual TLS or a service token; the token alone does not encrypt). Not
prevented by this change: a risk line in ADR-0009, with the deployment's TLS
as the mitigation.

## Modules

`doc_keys.py`, `api_originals.py` (seal only), `api_open.py` (open only), and
the additions to `config.py`. Each ≤ 200 lines. Decided after the reviewer's
FAIL on wordsworth#544, where a single `api_originals.py` holding both routes
came out at 202 lines: the split is the design, not a fallback. Seal stays in
`api_originals.py`, open lives in `api_open.py`; neither route is moved back
to make a file shorter or longer.

## Risks

- **The 413 comes after the body is buffered.** `KEYSERVICE_MAX_ORIGINAL_BYTES`
  is enforced once FastAPI has read the whole body into memory, so an
  oversized request still costs that memory before it is refused. Accepted:
  every caller is wordsworth, behind a service token, and the ingress body
  limit is the real bound. The same sentence goes in the PR description.

## Open questions

- **`open` does not check `known_documents.deleted_at`** (for
  `key-service-delete`, #540). It is unreachable now: nothing tombstones a
  document yet. It must be settled before deletion can tombstone without
  destroying every key row; until then no requirement says `open` refuses a
  tombstoned document.
