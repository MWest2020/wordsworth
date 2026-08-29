---
status: accepted
last_reviewed: 2026-08-29
---

# ADR-0003: Verifiable-credential reveal authorization (EUDI-aligned), PoC-first

## Context

Reveal in wordsworth is today gated by per-department **grants** plus
per-type keys (Fase B, see `ADR-0002`): a caller presents a grant
(currently a tailnet-internal `grant_id` bearer capability) and, if its
`allowed_types` and the key availability permit, OpenBao unwraps the
per-object data key and the selected PII types are revealed. Authorization
is thus a static, server-issued capability.

The sovereignty story we tell (`demo`: "Waarom dit soeverein is") is that
the **data owner holds the keys** — the KEK never leaves OpenBao, and
re-identification is a deliberate, authorized act. A natural next step is to
let the *authorization* itself be something the authorized party **holds and
presents**, rather than a capability the server hands out — e.g. an official
proving "I am HR-authorized", or a data subject proving "I am the person",
via a credential in their own wallet.

The **EU Digital Identity Wallet (EUDI)** ecosystem (eIDAS 2.0, Regulation
(EU) 2024/1183) is directly relevant for Dutch-government use: it is
open source (reference implementation under `eu-digital-identity-wallet`,
Apache-2.0 / EUPL — the latter aligns with wordsworth's EUPL-1.2) and built
entirely on open standards — **OpenID4VP / OpenID4VCI**, **SD-JWT-VC**,
**ISO/IEC 18013-5 mdoc**, **W3C Verifiable Credentials**.

Crucially, EUDI is an **identity/credential wallet, not a KMS**. It proves
*who you are / what you may do* via credentials with selective disclosure;
it does not manage arbitrary envelope keys. So it complements, not replaces,
OpenBao.

## Decision

Adopt verifiable-credential-based reveal authorization the same way this
project already treats NiFi and Kafka (`ADR-0001`): **adopt the open
protocol first, loosely coupled; bring in the heavy reference stack only
when scale/requirements demand it.**

Concretely, in two stages:

1. **PoC (now).** Build a standalone **OpenID4VP + SD-JWT-VC verifier** that
   gates the reveal endpoint. A caller presents a verifiable presentation;
   wordsworth verifies the issuer signature and the selectively-disclosed
   claims (e.g. `role` / `authorized_types`) and maps them onto the existing
   grant `allowed_types` before OpenBao unwraps. OpenBao stays the KMS; the
   grants model is the integration seam.
2. **EUDI reference stack (when needed).** Only once the PoC proves the flow
   and there is a real need (production, cross-organisation, citizen-held
   credentials), integrate the EUDI reference verifier libraries, real
   issuer / eIDAS trust-list handling, mdoc/ISO 18013-5, and actual wallets.

### PoC scope

In scope:
- A verifier module (opt-in, config-gated like `WORDSWORTH_REVERSIBLE` —
  **default off**, so the straat never depends on it and a failure here never
  stops the pipeline — see the resilience invariant).
- SD-JWT-VC as the first credential format (lightest; mature JVM/Python libs).
- Verify signature + selective-disclosure claims → derive authorized types →
  reuse the existing grant / `allowed_types` path into OpenBao.
- A **dev-only local test issuer** to mint SD-JWT-VCs (no real EUDI issuer infra).
- TDD, with the CARDINAL invariant intact: no clear PII in logs/audit; the
  audit records the credential-derived caller, never clear values.

Out of scope for the PoC:
- Mobile wallet apps, secure element / WSCD, device binding.
- Real eIDAS trust lists and production issuers.
- mdoc / ISO 18013-5 (SD-JWT-VC first; mdoc is a later add).

## Consequences

- **Positive.** Keeps OpenBao as the single KMS; extends (does not rewrite)
  the grants model; loosely coupled and standards-first, so we are not locked
  to the EUDI reference implementation's timeline (still maturing toward the
  ~2026 rollout); aligns the sovereignty narrative with a citizen/official
  who holds their own credential; EUPL alignment eases later reuse.
- **Negative / cost.** Adds a JOSE / SD-JWT-VC verifier dependency, but only
  in the opt-in reveal path. Introduces a second authorization mechanism
  alongside grant bearer capabilities during the PoC; the two must reconcile
  cleanly (VC presentation → grant `allowed_types`).
- **Neutral.** No change to ingest, pseudonymization, index, or search. This
  ADR is `proposed`; it moves to `accepted` when the PoC lands green.

## Alternatives considered

- **Full EUDI reference stack now** — rejected: too heavy (apps, issuer infra,
  secure elements) and still maturing; violates the PoC-first / loose-coupling
  pattern of `ADR-0001`.
- **Keep only static grant capabilities** — viable, but misses the
  holder-presents-a-credential sovereignty step and the EUDI alignment that
  Dutch-government deployment will eventually want.
- **Roll our own token format** — rejected: reinvents OpenID4VP / SD-JWT-VC
  and forfeits interoperability with the EUDI ecosystem.
