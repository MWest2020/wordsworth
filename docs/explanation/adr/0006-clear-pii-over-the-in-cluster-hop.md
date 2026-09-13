---
status: accepted
last_reviewed: 2026-09-13
---

# ADR-0006 — Clear PII crosses one in-cluster hop over http

## Context

Anonymisation is the whole promise: nothing with personal data reaches the
index, the object store or a model. There is exactly one place where that
promise is in transit rather than kept — the ingest POSTs the **raw extracted
text**, still containing PII, to the OpenAnonymiser service over in-cluster
`http://`:

    WORDSWORTH_OPENANONYMISER_URL:
      http://openanonymiser.openanonymiser.svc.cluster.local:8080

Everywhere else the data is either already de-identified (index, S3, RAG) or
encrypted at rest (the mapping store). This hop is the exception, and until now
it lived as a bullet in `deploy/README.md` under "hardening follow-ups" — a note,
not a decision. A note has no owner and no expiry; it is how a known weakness
becomes an old weakness.

## Decision

**Accept the plaintext hop for a single-tenant cluster, and name the condition
under which it stops being acceptable.**

The condition, explicitly: **the moment this cluster carries a second tenant, or
any workload not operated by the same party, this becomes a blocker.** Not a
follow-up — a blocker, in the same sense as "no clear PII to the index".

Until then the mitigation is the boundary, not the transport: the pod network
belongs to one operator, the service is not exposed outside the cluster, and the
call never leaves it.

## Why not mTLS now

A service mesh to protect one hop adds more new surface than it removes. It
brings sidecars or a CNI-level encryption layer, certificate rotation, and a
second failure mode for every call in the cluster — and the thing it protects
against (another tenant sniffing pod traffic) does not exist here yet. That is
the clever-instead-of-boring trade this repository rejects elsewhere; there is no
reason to make it here.

The cheap step, when the condition triggers, is not a mesh: set
`WORDSWORTH_OPENANONYMISER_URL` to `https://…` and give the service a
certificate. httpx verifies by default, so the client side needs no change. That
is the intended path, written down so the next person does not start by
evaluating meshes.

## Consequences

- `deploy/README.md` points here instead of carrying the reasoning.
- A second tenant on this cluster is a **blocking** change, not a nice-to-have.
- If anyone proposes a mesh for this hop alone, this ADR is the answer; if the
  condition above has triggered, this ADR is superseded rather than argued with.

## Alternatives considered

- **mTLS via a service mesh** — declined, see above.
- **In-process anonymisation** (no network hop at all) — declined by ADR-0001 and
  ADR-0004: OpenAnonymiser is a separate, independently deployable component, and
  folding it in would put an ML runtime inside the API image.
- **Encrypt the payload at the application layer** — declined: that is TLS with
  extra steps and a key-management problem of its own.
