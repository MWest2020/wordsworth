# Tasks — fix-eval-per-query-ap-label

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
Fixes #20 (part 2).

## 1. Per-query key is `ap`, aggregate is `map`
- [ ] 1.1 Store per-query Average Precision under `ap`; keep the aggregate mean as
      `map`; update the `_METRICS`/aggregate wiring accordingly
- [ ] 1.2 Tests: per-query rows carry `ap`; the aggregate carries `map`; numeric
      values unchanged
