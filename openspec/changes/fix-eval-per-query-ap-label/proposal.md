## Why

Fixes issue #20 (part 2). The evaluation harness stores each query's Average
Precision under the key `map` (`src/wordsworth/eval/harness.py`). MAP is the
**mean** of AP over queries, so it is meaningful only at the aggregate level; at
the per-query level the value is AP. The mislabel makes a per-query AP
indistinguishable by name from the aggregate MAP. No numeric error — the metric
math and the aggregate mean are correct.

## What Changes

- Per-query results SHALL report Average Precision under the key `ap`; the
  aggregate mean of AP SHALL be reported as `map`.

## Capabilities

### Modified Capabilities
- `evaluation`: per-query AP is keyed `ap`, aggregate MAP stays `map`.

## Impact

- Corrects the per-query key in `src/wordsworth/eval/harness.py` and the tests
  that assert `per_query[...]["map"]`. Metric functions unchanged. Does not touch
  `CLAUDE.md`, `.claude/agents/`, or CI.
