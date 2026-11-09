# originals-ingest-switch

## Why

Step 4 of 4 (`originals-ingest-seam` → `originals-ingest-readers` →
`originals-ingest-write` → **`originals-ingest-switch`**). Readers open sealed
originals and ingest writes them, but only when handed an `OriginalsStore`.
This step hands it one in the running service and the CLIs. That makes ADR-0008
true for new documents: every new original is stored sealed. It also brings
the docs.

## What changes

- **`serve.build_app`.** When the object store is configured, it builds one
  process-lifetime `OriginalsStore(S3ObjectStore, DocumentKeys(transit_for))`,
  with `transit_for` from `transit.transit_factory(settings.openbao_url,
  settings.openbao_token)`.
  - This applies in reversible **and** irreversible mode, so there is one
    unwrap cache per process.
  - It passes the `OriginalsStore` to `create_app` as `store`. The reversible
    wiring shares the same `transit_for` (step 1).
- **`originals_io.originals_from_config(store)`** builds the same thing for
  the CLIs. `ingest_corpus.py` and `ingest_manifest.py` use it where they now
  build a bare `S3ObjectStore`, and neither builds a transit itself.
  - `reprocess.py` is not in this list: it builds no store and has no entry
    point. Its store comes from `api.py` via `build_app`, and the k8s job only
    POSTs `/reprocess`. So `build_app` covers it.
- **The OCR gap is pinned.** A test asserts that recovery's OCR write is still
  plaintext (no sealed header) and still reads through `read_original`. Its
  docstring names `originals-ocr-sealed` as the change that inverts it.
- **Docs.**
  - `docs/how-to/originals-encryption.md`, new:
    - ingest order and rollback;
    - the 503 and the batch stop, with the body from `originals-ingest-write`.
      An empty `openbao_token` or an unreachable OpenBao gives 503 on every
      ingest, by design: there is no plaintext fallback. Rollback is the
      previous wordsworth image digest in homelab;
    - the OCR gap until `originals-ocr-sealed`;
    - the deploy precondition below.
  - `docs/reference/ingest.md`: the 503 body.
  - `docs/reference/architecture.md`: ingest order, and that every reader
    opens through the seam. Extend what is there; don't duplicate.
  - `docs/reference/cli.md`: the non-zero exit on an unavailable key.
- **Roadmap.** `docs/reference/roadmap.yml`: the item "New originals stored
  encrypted … every reader opens them" becomes done, with this change as
  evidence. The item's wording does not claim that new originals are
  encrypted yet: that is true only after the digest bump below.
- **`docs/reference/cli.md`, the 503 gap.** The sentence that tracks the
  CLI's missing stop on 503 for this change is corrected: the gap lives in
  `client.py` and is not fixed here; it points at a follow-up issue.

## Deploy precondition (not a build task)

Merging this change does not deploy it. Wordsworth images reach the cluster
through a digest bump in homelab. Before that bump, both of these must exist,
with the evidence in the homelab PR. They are deploy preconditions in that PR,
not build tasks in this change, and no task here produces them:
- a restore-tested backup of the `document_keys` table;
- an off-node OpenBao snapshot that holds the originals KEK.

Without them, a lost key row or KEK makes a sealed original unreadable for
good.

Default if that evidence isn't there: the image is not rolled out, and new
documents stay plaintext until it is.

## Depends on

`originals-ingest-write`.

## Out of scope

The OCR write (`originals-ocr-sealed`, next), destroying keys on deletion
(`originals-crypto-shred`), sealing the existing corpus
(`originals-encrypt-existing`), and the CLI's 503 handling in `client.py`
(follow-up issue, linked from `docs/reference/cli.md`).
