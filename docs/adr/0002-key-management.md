# ADR 0002 — Sovereign key management for reversible pseudonymisation

- Status: accepted
- Date: 2026-08-20
- Context: Fase B (reversible pseudonymisation + key-gated selective reveal)

## Context

Reversible pseudonymisation stores, per PII type, an AES-256-GCM ciphertext of the
original value keyed by a per-type data key (see the `pseudonymization` and
`key-lifecycle` capabilities). Until now the `KeyProvider` held those data keys
**in memory only** — they do not survive a restart, so nothing pseudonymised
could be revealed after the pod recycles. Key management is exactly the aspect on
which prior government attempts stalled, so it must be durable, sovereign, and
auditable, using open tooling (OpenBao / SOPS+age — never CyberArk/Conjur).

## Decision

**Envelope encryption with OpenBao Transit as the key-encryption key (KEK).**

- Wordsworth generates a fresh 32-byte **data key** per `(scope, version)` where
  scope is the PII type (`PERSON`, `BSN`, …). The data key encrypts that type's
  mappings (unchanged from today).
- Each data key is **wrapped** (encrypted) by OpenBao's Transit engine under a
  named KEK that never leaves OpenBao. Only the *wrapped* blob is persisted, in a
  durable `key_vault` table (`key_id`, `scope`, `wrapped_material`, `status`
  active/retired, `created_at`). Clear data-key material is never written to disk.
- To use a key, Wordsworth calls Transit **unwrap**; unwrapped material is cached
  in memory with a short TTL so the hot path does not hit OpenBao per call and a
  brief OpenBao blip does not stall the straat (resilience, ADR-0007/cycle 7).
- This slots behind the existing seams: a `DurableKeyProvider` implements
  `KeyProvider` (current_key/key/rotate per scope) over the vault + Transit, and
  the `Escrow` seam is satisfied by "the wrapped keys in `key_vault` + the OpenBao
  KEK". Rotation mints+wraps+stores a new active version; prior versions stay
  resolvable by `key_id` (so existing mappings still decrypt).

**Authentication.** Wordsworth authenticates to OpenBao with a scoped AppRole/
token limited to Transit wrap/unwrap for its KEK — **never** the root token.

**Custody (the crown jewels).** OpenBao runs in-cluster on the homelab (this is
the lab/factory, not alma prod). Initialisation yields unseal shares + a root
token. For the lab:

- Initialise with a small set of unseal shares; **escrow the unseal material and
  root token out-of-band via the repo's SOPS+age flow** (age identity held by the
  operator, Mark) — never in plaintext in git or logs.
- A sealed OpenBao (after a restart) means reveal is **unavailable** (fail-closed;
  we never reveal without keys) and pseudonymising a not-yet-keyed type **blocks**
  (fail-hard; no clear PII reaches the index). Both are consistent with the
  sovereignty invariants — degrade safely, never leak.

Production (alma, out of scope here and off-limits to this workstream) MUST harden
this: **auto-unseal** (Transit auto-unseal from a separate OpenBao, or an HSM/KMS)
and **split custody** of unseal shares among multiple custodians.

## Alternatives considered

- **OpenBao KV holding raw data keys** — simpler, but the data keys then live only
  in OpenBao with no local wrapped-key vault, and it is not "envelope" encryption.
  Rejected in favour of Transit-wrapped keys in a durable vault (matches the
  key-lifecycle spec's "envelope encryption of the data keys").
- **SOPS+age for the data keys directly** — good for static bootstrap secrets, but
  it has no rotation/unwrap-on-demand story for per-type versioned data keys.
  Retained only for escrowing OpenBao's own unseal material.

## Consequences

- New durable `key_vault` table; a Transit client; a `DurableKeyProvider`; config
  for the OpenBao URL, auth, KEK name, and cache TTL. Built behind the existing
  seams, so the pipeline and reveal API are unchanged in shape.
- Reveal and new-type pseudonymisation depend on OpenBao availability; the
  in-memory unwrap cache and fail-closed/fail-hard behaviour bound the blast
  radius. Grants (revocation) remain the primary reveal gate; key retirement is
  the cryptographic backstop.
- Code is provable in CI against a **fake in-memory Transit** (same wrap/unwrap
  contract); a real OpenBao is deployed and smoke-tested separately.
