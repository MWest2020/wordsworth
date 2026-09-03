## 1. Lists

- [x] 1.1 `detection_lists.py`: load `allow.json`/`deny.json`, validate, sha256
  logged at start; `apply(detections) -> detections` pure.
- [x] 1.2 Hook after detection in the reversible path (allow+deny) and before the
  engine in the irreversible path (deny only);
  `suppressed_by_list` in audit aggregates.

## 2. Feedback

- [x] 2.1 `POST /documents/{id}/feedback` → audit record, no clear values.

## 3. Gate

- [x] 3.1 Tests; docs `docs/how-to/detection-lists.md`. Suite + CI green;
  `openspec validate add-detection-feedback`.
