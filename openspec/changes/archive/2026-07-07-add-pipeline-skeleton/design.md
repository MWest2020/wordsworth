# Design decisions — add-pipeline-skeleton

## State machine

```
registered ──(profile)──┬─▶ extractable ──(extract*)─▶ extracted
                        │                     │
                        ├─▶ unprocessable_ocr └─(anonymize*)─▶ anonymized
                        │      (terminal)              │
                        └─▶ failed(reason)             └─(index*)─▶ indexed
   any state ──▶ failed(reason)                                     (terminal)
```

`* ` = stub transition in this change; real work lands in (c)/(b)/(d).

No resting `profiled` state: profiling is the transition out of `registered`,
and its result *is* the next state. The audit record for that transition
carries the metric, so a separate resting state would be redundant.

## Decision 1 — single global hash chain

Record: `seq, document_id, from_state, to_state, ts, step, payload, prev_hash, hash`
with `hash = sha256(prev_hash ‖ canonical_json(record_without_hash))`.

At ~1–2k docs × ~5 transitions ≈ 5–10k appends per nightly batch, tail
contention on one chain is negligible and the chain is verifiable by hand.

**Clever pitfall rejected:** per-document chains or a Merkle tree "for scale" —
buys parallelism we do not need at this volume, at the cost of a verification
nobody can walk by hand. Revisit only if measured append throughput demands it.

## Decision 2 — PostgreSQL authoritative, JSONL derived

The append-only PostgreSQL table is the single source of truth (orchestration
+ audit). The hash-chained JSONL inherited from Zeef is a derived append-only
*view* (same records, same hashes) feeding the future WORM/object-lock export.

**Pitfall rejected:** dual source of truth (write both, reconcile) — a
consistency trap. One writer, one truth; JSONL is projection only.

Consequence: `documents.current_state` is **derived** from the latest audit
record, never stored as a mutable column — otherwise the state column becomes a
second, mutable source of truth. At ~1–2k docs the query cost is irrelevant; if
it ever matters, a read-model/materialized view is the boring fix, not a mutable
column.

## Decision 3 — atomic transition = idempotent + resumable

State transition and audit append happen in one PostgreSQL transaction. A
worker that crashes mid-run resumes from the last committed state; a transition
whose target state is already passed is a no-op. This is the whole of the
"orchestration" — no engine.

## Decision 4 — born-digital detection (pypdf, BSD)

- Parse all pages, count extractable characters. Metric = chars / page.
- Below config threshold `T` → `unprocessable_ocr`; at/above → `extractable`.
- Store raw `chars`, `pages`, `bytes` in the audit payload. Re-classifying at a
  different `T` reads audit data — no re-parse.
- **Parse crash → `failed(reason)`**, never silent `unprocessable_ocr`. Mirrors
  the null-vector rule: no silent fallback.
- **Profiling measures, does not extract.** It discards the text; real
  extraction is the later `extracted` transition with its own audit record.
  PoC cost: the PDF is parsed twice (~1–2k docs, CPU nightly — acceptable). If
  throughput bites, deterministic page sampling (first N + evenly spaced, never
  random) is the first lever. Not built pre-emptively.

## Rejected dependency

PyMuPDF (fitz) is faster but AGPL — copyleft risk in a sovereign EUPL-1.2 tool.
pypdf (BSD) is enough: detection only counts, it need not render prettily.
pdfplumber (MIT) is held as a candidate for the real `extracted` step if layout
matters there.
