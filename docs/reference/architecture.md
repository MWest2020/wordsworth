---
status: draft
last_reviewed: 2026-07-12
---

# Architecture reference

Distilled from the [README](../../README.md) and the project brief. Migrated
without a content review, so this page is `draft`; a real review promotes it to
`current`.

## Pipeline

wordsworth is a single linear pipeline:

```
ingest → text extraction (pdfium) → anonymize/pseudonymize → store → index → hybrid search → rank
```

Text extraction is the single `positioned_text` function (pypdfium2,
`text_source` `pdfium-v1`): profiling, detection, the stored text, the index
text and the redacted-PDF box map all read it, so a value detection finds
cannot fail to exist in the text the box map searches
(pdf-redaction-locate).

What a consumer does with the documents afterwards is out of scope — wordsworth
is the engine. Reference case: Woo-request handling for a Dutch municipality.

## Invariants

- **No clear PII toward the search index.** Anonymization is irreversible;
  pseudonymization is controlled and reversible and sits *before* indexing.
- **Append-only, hash-chained audit trail** over every transformation, from day
  one; PostgreSQL. No `UPDATE`/`DELETE` on audit records. The audit table is the
  document state machine — `documents.current_state` is derived from the latest
  audit record, never stored as a mutable column. There is no separate workflow
  engine.
- **Deleting a document deletes its content, never its row.** `deleted` is a
  state like any other, terminal and reachable from every state (including
  `superseded`) — there is no restore path. The `documents` row and every
  earlier audit record stay, because the audit table's `document_id` is a
  non-null foreign key and the trail never deletes a record; what goes is the
  stored object, the stored text, the pseudonyms, the mappings, the index
  entry and the grants. The one `deleted` audit record holds ids and counts
  only, written in the same transaction as the removal — see
  [deleting documents](../how-to/deleting-documents.md).
- **A failed embedding is a hard error, never a silent fallback.** No silent
  fallbacks anywhere. A transport failure (the embedding service unreachable,
  timed out, a 5xx, a response cut off) is retried within the bounded retry
  budget first — with two Ollama instances the retry usually reaches the other
  one — and is a hard error after it. That holds for a document's embedding at
  ingest and for a query's (`hybrid_search`: `/hybrid`, console search, `/ask`).
  A bad embedding is never retried. Every retry is a JSON log line
  (`"event": "retry"`, and `"retry_exhausted"` when the budget runs out) naming
  what was retried and the exception's class, never its message: a message can
  quote the document. Every state transition is a JSON line too (`"event": "transition"`,
  at INFO). The api prints both to stderr; until 2026-09-26 nothing attached a
  handler, so transitions were written and never seen.
- **No cloud APIs in the critical path.** Embeddings and any LLM run locally.
- **Driver/protocol pattern for every adapter** (anonymization, key/mapping
  store, object storage, search, embeddings).
- **Born-digital only for the PoC.** Scanned PDFs move to `unprocessable_ocr` in
  the audit trail; OCR is MVP-backlog.
- **Files ≤ 200 lines.**

## Stack

- Python 3.12+, managed with `uv` (never `pip`); FastAPI; pydantic v2.
- PostgreSQL. S3-compatible object storage (Ceph RGW target, SeaweedFS PoC).
- OpenSearch for BM25 (phase 3) and dense + hybrid/RRF (phase 4).
- Local inference: Ollama (bge-m3) for embeddings; GLiNER/Presidio via
  OpenAnonymiser for PII detection.

## Storage

Original PDFs are sealed under their own data key before they reach the
object store ([ADR-0008](../explanation/adr/0008-envelope-encryption-of-originals.md)):

- **Format.** A sealed object carries a versioned header (`WWENC`, a version
  byte, the 12-character data-key id, a 12-byte nonce) followed by
  AES-256-GCM ciphertext. The associated data binds the ciphertext to the
  object key and the key id — never the document id, because one object can
  belong to more than one document over its life (a superseded copy, a
  re-ingest after deletion). `src/wordsworth/originals_envelope.py` holds
  `seal`/`open` and the header; nothing else.
- **`document_keys`.** One row per sealed *object* (not per document — an
  OCR-recovered document has a scan and an OCR'd PDF, each with its own key),
  holding the data key wrapped by a KEK in OpenBao Transit. The KEK is named
  per pseudonymisation domain (`src/wordsworth/document_keys.py`,
  `DocumentKeys`), so a KEK-per-organisation is a configuration change, not a
  rewrite. The unwrap cache is bounded in size and time (`key_cache_ttl`), so
  a revoked or rotated KEK takes effect within that window.
- **`OriginalsStore`** (`src/wordsworth/originals_store.py`) is the only way
  an original is written or read: `put_original` never mints a second key for
  an object and never overwrites bytes a document can still read (its result
  is a `PutResult` — `WROTE`, `UNCHANGED` or `LEGACY` — with no boolean
  value, so a caller cannot accidentally delete a legacy object after a
  failed commit); `get_original` opens a sealed object or returns a legacy
  plaintext object as it is.
- **The plain `ObjectStore.get` refuses a sealed object**, raising
  `SealedObjectError`, so ciphertext can never reach a caller expecting a PDF
  by accident. The unguarded `get_raw` exists for the three callers that need
  the sealed bytes or the header: `OriginalsStore`, `put_original`'s own
  inspection, and the orphan sweep below.
- **`wordsworth-sealed-orphans`** (`src/wordsworth/sealed_orphans.py`) removes
  sealed objects older than one hour that open under no key row — the result
  of a database transaction that rolled back after the object was already
  written (S3 and Postgres cannot share one transaction). Dry-run by default;
  see [the how-to](../how-to/sealed-orphans.md).
- **Nothing is sealed in production yet.** This module builds the cipher and
  the key store only; ingest and every read site (`pipeline.py`, `recovery.py`,
  `api.py`) still read and write plain objects until `originals-encrypted-ingest`
  and `originals-ocr-sealed` wire them in.

## Configuration

- **Secrets** via SOPS+age or OpenBao only — never hardcoded, never client-side,
  never a commercially licensed store.
- **License:** MIT. All code and dependencies must be license-compatible;
  AGPL is rejected where it would infect distribution.
- **Banned dependencies:** `anonypy`; MinIO (open-source edition deprecated
  April 2026 — use Ceph RGW or SeaweedFS behind the S3 seam); CyberArk/Conjur.
- **Originals KEK** (ADR-0008, next to `WORDSWORTH_TRANSIT_KEK` and
  `WORDSWORTH_KEY_CACHE_TTL`): `WORDSWORTH_ORIGINALS_KEK` names the Transit
  KEK that wraps original-document data keys (default: the same KEK as the
  pseudonymisation keys); `WORDSWORTH_ORIGINALS_KEK_BY_DOMAIN` is an optional
  JSON object (domain → KEK name) overriding it per pseudonymisation domain —
  the lever that turns a KEK-per-organisation into a configuration change.
  `WORDSWORTH_DOCUMENT_KEY_CACHE_SIZE` bounds the unwrap cache's entry count
  (default 1024); its time bound is the existing `WORDSWORTH_KEY_CACHE_TTL`.

## Working on this

`uvx ruff check src/ tests/` before opening a PR. Deliberately narrow — `F` and
`E9`, real errors only, no style. A linter that argues about taste gets switched
off, and then it never catches the things it is for: its first run found a
protocol stub that had landed inside an implementation class and shadowed it,
and a test whose comment claimed a sanity check it did not make.

One token, one place that reads it: `pseudonymizer.label_of()`. The same
`[LABEL:hash]` parse used to live in four places, and a change to the token shape
would have found three of them.

## Reused components

- [OpenAnonymiser](https://github.com/ConductionNL/openanonymiser_light)
  (EUPL-1.2) — anonymization adapter (Presidio + GLiNER + deterministic regex;
  BSN elfproef, IBAN mod-97). EUPL is fine here precisely because it is reached
  over HTTP as a deployed service and never linked in: that is what keeps the
  MIT invariant intact.
- [zeef](https://github.com/MWest2020/zeef) (MIT) — ranking (local Ollama
  embeddings, cosine, UPGMA clustering, append-only audit-JSONL).
