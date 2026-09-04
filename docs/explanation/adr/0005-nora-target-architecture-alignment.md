---
status: accepted
last_reviewed: 2026-09-03
---

# ADR-0005: Alignment with the NORA "bij de Bron" target architecture — what wordsworth adopts, adapts, and declines

## Context

The NORA Expertgroep deck "Anatomie van Anonimiseren & Pseudonimiseren bij de
Bron" (Haarlem/Zandvoort) describes a municipal target architecture for
reversible anonymisation of documents and NEN 7524-style pseudonymisation of
datasets. `docs/explanation/nora-gap-analysis.md` tests wordsworth against it.
Most gaps fit wordsworth's invariants and are proposed as OpenSpec changes.
Eleven points do **not** fit and need an explicit decision; this ADR records
the recommendation per point so the decisions are made once, in one place.

## Decisions (each: deck position → recommendation → why)

**D1 — RDFa-embedded ciphertext in the document.** Deck: PII encrypted and
embedded inline as an RDFa `<span>` with `data-encrypted-value`. Recommend:
**decline inline ciphertext; offer RDFa as an export view.** wordsworth's
separated mapping store is the reason key rotation never touches documents and
the reason the index never sees ciphertext churn. An RDFa export
(`?view=rdfa`) can carry `typeof`, `data-entity-type`, `data-legal-basis`,
`data-key-id` and the token — everything except the ciphertext — and stays
interoperable with a DMS that wants RDFa.

**D2 — Per-document keys derived from a category key.** Deck: document key =
KDF(category key, doc id), never stored. Recommend: **decline; keep random
per-scope keys with rotation + escrow, add the domain dimension**
(`add-domain-keys`). Derived per-document keys make rotation a re-derivation of
every document and contradict the deck's own "wrapping, not derivation" note.
The deck's goal (attribute *which* key, *when*, *by whom*) is met by `key_id`
per mapping plus the key-lifecycle audit stream.

**D3 — Algorithm per AVG article (AES-256-GCM / ChaCha20-Poly1305 / RSA-OAEP).**
Recommend: **decline.** One AEAD (AES-256-GCM) for all categories; the legal
basis is metadata (`add-pii-categories-and-ppl`), authorisation is the grant.
Three ciphers add surface without adding protection — the article is a policy
attribute, not a cryptographic one — and RSA-OAEP for bulk field encryption is
the clever pitfall (it needs a hybrid scheme anyway). Boring and auditable wins.

**D4 — Anonypy as detection layer 2.** Recommend: **decline** (already banned in
CLAUDE.md). The "Swiss Cheese" property is met by regex + Presidio patterns +
NER (OpenAnonymiser); name it as such in docs, measure it with
`add-pii-detection-eval`.

**D5 — HSM (FIPS 140-2 L2) master key.** Recommend: **out of core** — OpenBao
auto-unseal/HSM is deployment hardening (ADR-0002). No code change.

**D6 — TTP key hand-over via PKCS#12.** Recommend: **adapt** — export a
domain key as an age-encrypted envelope (the existing escrow format) plus a
JSON metadata file; do not implement PKCS#12, which is designed for X.509
private keys/certs and has poor support for symmetric "secret bags". The
requirement behind it (a new vendor or a TTP can reproduce the same
pseudonyms) is met by exporting the *wrapped domain key* and the normalisation
profile version.

**D7 — ABAC / Entra ID / SSO / roles.** Recommend: **defer**, keep the grant
capability model and add PPL as shorthand (`add-pii-categories-and-ppl`). A
real caller-auth model for the grant surface is already an open decision
(`docs/how-to/grants.md`); an IdP integration should be one change with its own
ADR, not a side effect of this alignment.

**D8 — Datasets (CSV) in scope.** Deck: half the platform is column-selected
pseudonymisation of tabular data. Recommend: **accept as a scope extension**
(`add-dataset-pseudonymisation`), because the value is that a BSN in a document
and the same BSN in a dataset get the *same* pseudonym under the same domain
key — that only works if both paths share one engine. Boundaries: CSV only, no
scheduling, no DWH delivery (NiFi's job), no Excel.

**D9 — NEN 7524 conformance.** Recommend: **implement the deck's header format
as "NEN 7524-style", label conformance unverified** until the norm text has
been checked. The repo must not claim compliance with a standard nobody has
read.

**D10 — Thin-client: detection + Web Crypto encryption inside a Word plugin.**
Recommend: **decline for wordsworth.** Keys never leave OpenBao (ADR-0002); a
plugin is an experience layer (ADR-0004) that calls the API. Client-side
detection would also fork the detector from the audited server path.

**D11 — Rendered outputs (DMS new version, Woo portal PDF/docx, TMLO metadata).**
Recommend: **out of core.** wordsworth emits de-identified text, JSON and
(with `add-legible-placeholders`) a legible view; re-rendering a docx/PDF with
placeholders is a separate render component behind the API, like the console.

## Consequences

- Eight OpenSpec proposals implement the compatible gaps; the order is in the
  gap analysis §3.
- Anything declined here stays declined until this ADR is superseded; a
  future stakeholder asking for RDFa-inline ciphertext or per-article ciphers
  is pointed at D1/D3 rather than re-litigating in a PR.
- The deck remains a *reference* architecture; wordsworth's contract is
  CLAUDE.md + the specs.

## Status update

Proposed 2026-09-03. **Accepted 2026-09-03 by Mark** (in #wordsworth): D8
(datasets in scope) accepted explicitly; D1–D7 and D9–D11 accepted as
recommended. Go given for proposals 1–5 (`add-value-normalisation`,
`add-pii-categories-and-ppl`, `add-detection-confidence`,
`add-legible-placeholders`, `add-domain-keys`); 6–8 stay at propose stage.
