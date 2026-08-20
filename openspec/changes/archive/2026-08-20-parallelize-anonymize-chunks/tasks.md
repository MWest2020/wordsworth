## 1. Concurrent chunk dispatch

- [x] 1.1 `_openanonymiser_redact` dispatches chunks via a bounded thread pool
  (`min(len(chunks), anonymize_concurrency)`), reassembling in chunk order.
- [x] 1.2 Fail-hard preserved: a failing chunk propagates (no partial output).
- [x] 1.3 `WORDSWORTH_ANONYMIZE_CONCURRENCY` default 1 → 3.

## 2. Deploy

- [x] 2.1 OpenAnonymiser `replicas: 3` + `podAntiAffinity` on hostname.
- [x] 2.2 Lower memory/CPU limits (12Gi→4Gi, cpu 2→1) — chunking bounds the peak.

## 3. Gate

- [x] 3.1 Tests: order preserved under out-of-order completion; failing chunk
  propagates; reassembly + count-sum still hold.
- [x] 3.2 Full suite green (176 passed) + `openspec validate` clean.
- [x] 3.3 Deployed; three replicas Running one-per-node; measured 2.15× on an
  18-chunk / 70k-char doc (485.9s serial → 225.8s at concurrency 3).
