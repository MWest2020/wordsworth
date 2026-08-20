## Why

Anonymize was the pipeline bottleneck at ~40s/document. The homelab is HA (6
nodes) but each worker node has only **1 CPU** (3 usable worker cores total;
control planes are tainted), so a single OpenAnonymiser replica pins one core and
each GLiNER forward pass is single-core-bound. Vertical scaling is impossible
(nodes are 1 CPU); document-level parallelism is blocked by the intentional
global audit hash-chain lock (a single `pg_advisory_xact_lock` held for the whole
per-document transaction). A document's chunks, however, are mutually independent
and are anonymized *before* the audit transition — so they can run concurrently
without touching the chain lock, spreading one document's work across replicas.

## What Changes

- The driver dispatches a document's chunks concurrently (bounded by
  `anonymize_concurrency`, the same cap the process-wide `limiter` already
  enforces) instead of serially, and reassembles the redacted pieces in chunk
  order. Fail-hard is preserved: if any chunk fails, the exception propagates and
  the caller raises `AnonymizationEngineError` — no partial, un-redacted text is
  ever emitted.
- `WORDSWORTH_ANONYMIZE_CONCURRENCY` default 1 → 3 (the worker-node count), so a
  document's independent chunks spread one-per-replica across the cluster.
- OpenAnonymiser scales to `replicas: 3` with `podAntiAffinity` on
  `kubernetes.io/hostname` (one per worker node); the Service load-balances the
  concurrent chunk calls across them.
- OpenAnonymiser memory limits drop (12Gi → 4Gi): driver-side chunking already
  bounds each call's O(n^2) attention spike, so the OOM headroom is unneeded and
  three replicas fit alongside OpenSearch/Ollama/Postgres on the 16Gi nodes. CPU
  limit is 1 — all a node has.

## Capabilities

### Modified Capabilities
- `deployment`: the anonymize step uses the cluster's aggregate CPU by fanning a
  document's chunks across replicas concurrently, bounded and order-preserving,
  with unchanged fail-hard and audit-serialization guarantees.

## Impact

- Code: `openanonymiser_driver.py` (`_openanonymiser_redact` concurrent dispatch),
  one config default. No pipeline/schema/audit change; composite, fail-hard, and
  the process-wide concurrency cap are unchanged. Tests added (order preservation
  under out-of-order completion; a failing chunk propagates).
- Deploy: `homelab` `openanonymiser.yaml` — replicas 3, anti-affinity, lower
  memory/CPU limits.
- Ceiling is modest (~2×, not linear): the 3 worker cores are shared with
  OpenSearch/Ollama/Postgres/MinIO. This is the structural way to use the HA
  cluster's aggregate CPU, not a claim of linear speedup.
