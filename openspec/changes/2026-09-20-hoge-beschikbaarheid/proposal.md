# Proposal: wordsworth survives the loss of one node

## Why

Mark, 2026-09-20: *"is wordsworth btw High Availability?"* No. That same
afternoon the cluster VMs had to be restarted one by one, and when node-03
went, wordsworth was unreachable for minutes.

The first version of this proposal (2026-09-20) blamed a node-bound corpus
volume and made everything wait for movable storage. Measured again on
2026-09-23, the picture is different:

- **The api holds no state of its own.** It mounts only an `emptyDir` on
  `/tmp`; since key-audit-in-postgres even the key-lifecycle stream is in
  Postgres. Documents live in S3 (SeaweedFS), everything else in Postgres.
- **`wordsworth-corpus` is mounted by nothing.** A 5Gi `local-path` volume
  pinned to node-03, left over from before the object store.
- **Postgres already survives a node**: three CNPG instances with failover.
- **Every other component is one pod on one node's disk**, and `local-path`
  is the only storage class in the cluster:

| Component | Replicas | Node | Losing that node means |
|---|---|---|---|
| wordsworth-api | 1 | node-03 | no api, no console |
| wordsworth-auth (oauth2-proxy) | 1 | node-01 | nobody can log in |
| SeaweedFS (S3) | 1 | node-01 | stored documents unreachable |
| OpenSearch | 1 | node-02 | search degrades (handled since 3.1b) |
| Ollama | 1 | node-03 | no embeddings, no `/ask` |

So the api does not need to wait for storage. The object store does, and it is
the one piece whose loss takes documents with it.

## What Changes

**Step 1 — object storage that survives a node.** The decision is Mark's and
is homelab work. It covers two needs at once: the documents (S3 today, on
single-node SeaweedFS) and the WORM exports of both audit chains, which need
Object Lock. A candidate only counts once it has been shown to support Object
Lock; nobody has checked that for SeaweedFS yet. Both exports wait for this
decision.

**Step 2 — the api and auth survive one node.** Doable now, because neither
mounts a node-bound volume:

- api on two replicas with required anti-affinity per node, and a
  PodDisruptionBudget of `minAvailable: 1`, so a `kubectl drain` never takes
  the last one;
- the same for `wordsworth-auth`, whose sessions live in a cookie signed with a
  shared secret, so either replica can serve any user;
- whatever assumed one process now works across two: the rate-limit buckets
  move into Postgres (per-process buckets would give every client one bucket per
  replica, doubling every limit including the one on `/console/login`), and the
  mapping-store insert becomes one statement, so two requests pseudonymising the
  same value no longer fail one ingest.

**Step 3 — the dependencies.** OpenSearch with more than one node, Ollama as a
second instance or on storage that can move. Heavier than the api; after it.

**Step 4 — prove what we promise.** One test that takes a node out and checks
that the console keeps answering. Without it "highly available" is a word in a
document.

**Cleanup.** `wordsworth-corpus` is deleted once its contents have been
inspected and found to be unneeded.

## Scope / Not in scope

**In:** wordsworth's own shape — replicas, disruption budgets, placement,
state that has to be shared between replicas, and the requirement that the api
mounts no node-bound volume.

**Out:** building the storage layer (homelab), and Postgres HA, which exists.

## What keeps this honest

A second replica of the api is real redundancy only because the api mounts
nothing that is tied to a node, and the spec now says so as a requirement
instead of assuming it. A second replica still does not make wordsworth highly
available: with SeaweedFS, OpenSearch and Ollama each on one node, losing any
node still takes something down. Step 2 fixes the api's own node, which is what
broke on 2026-09-20; it is not the whole promise, and the documentation will
not claim more until step 4 has run.
