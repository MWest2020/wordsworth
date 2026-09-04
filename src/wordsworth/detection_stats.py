"""Per-layer detection aggregates for the audit trail (add-detection-confidence).

Answers "which layer found how much, how confidently" without ever recording a
value or an offset: ``{layer: {TYPE: {count, min_score, max_score,
below_threshold}}}``. The threshold only *counts* — it never weakens redaction
(a low-score entity is still replaced before anything reaches the index)."""
from __future__ import annotations

DETERMINISTIC = "deterministic"
OPENANONYMISER = "openanonymiser"


class DetectionStats:
    def __init__(self, min_score: float = 0.0) -> None:
        self._min = min_score
        self._d: dict[str, dict[str, dict[str, float | int]]] = {}

    def add(self, layer: str, entity_type: str, score: float, n: int = 1) -> None:
        if n <= 0:
            return
        cell = self._d.setdefault(layer, {}).setdefault(entity_type.upper(), {
            "count": 0, "min_score": score, "max_score": score, "below_threshold": 0})
        cell["count"] += n
        cell["min_score"] = min(cell["min_score"], score)
        cell["max_score"] = max(cell["max_score"], score)
        if score < self._min:
            cell["below_threshold"] += n

    def merge(self, other: dict) -> None:
        for layer, types in other.items():
            rows = self._d.setdefault(layer, {})
            for t, c in types.items():
                if t not in rows:
                    rows[t] = dict(c)
                    continue
                cell = rows[t]
                cell["count"] += c["count"]
                cell["min_score"] = min(cell["min_score"], c["min_score"])
                cell["max_score"] = max(cell["max_score"], c["max_score"])
                cell["below_threshold"] += c["below_threshold"]

    def to_dict(self) -> dict:
        return {layer: {t: dict(c) for t, c in types.items()}
                for layer, types in self._d.items()}
