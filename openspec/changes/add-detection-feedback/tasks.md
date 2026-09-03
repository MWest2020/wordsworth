## 1. Lists

- [ ] 1.1 `detection_lists.py`: load `allow.yml`/`deny.yml`, validate, sha256
  logged at start; `apply(detections) -> detections` pure.
- [ ] 1.2 Hook after detection in the reversible and irreversible paths;
  `suppressed_by_list` in audit aggregates.

## 2. Feedback

- [ ] 2.1 `POST /documents/{id}/feedback` → audit record, no clear values.

## 3. Gate

- [ ] 3.1 Tests; docs `docs/how-to/detection-lists.md`. Suite + CI green;
  `openspec validate add-detection-feedback`.
