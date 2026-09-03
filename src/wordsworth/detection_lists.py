"""Versioned allow/deny lists that refine detection (add-detection-feedback).

The boring alternative to a rules engine: two JSON files in a git-versioned
directory, loaded at start, content-hashed into every de-identify audit record.

``allow.json``  {"PERSON": ["^Jansen BV$", ...]}  — typed patterns whose match is
NOT PII of that type; a detection of that type whose value fullmatches is
dropped (never across types).
``deny.json``   {"KENTEKEN": ["\\\\b[A-Z]{2}-\\\\d{3}-[A-Z]\\\\b", ...]} — typed
patterns that ARE PII; every match becomes a detection (layer ``list``, score
1.0) in addition to what the detectors found.

Feedback (``POST /documents/{id}/feedback``) is recorded in the audit trail;
changing these files stays a reviewed git change by a human. No auto-learning."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .openanonymiser_driver import Entity

LIST_LAYER = "list"


@dataclass
class DetectionLists:
    allow: dict[str, list[re.Pattern[str]]] = field(default_factory=dict)
    deny: dict[str, list[re.Pattern[str]]] = field(default_factory=dict)
    hash: str | None = None  # sha256 over both files; None = no lists configured

    @classmethod
    def load(cls, directory: str | Path | None) -> "DetectionLists":
        """Read ``allow.json``/``deny.json`` from ``directory``; missing dir or
        files = empty lists. A malformed file or pattern is a hard error."""
        if not directory:
            return cls()
        base = Path(directory)
        digest = hashlib.sha256()
        parsed: dict[str, dict[str, list[re.Pattern[str]]]] = {}
        for name in ("allow", "deny"):
            path = base / f"{name}.json"
            raw = path.read_bytes() if path.exists() else b"{}"
            digest.update(name.encode() + b"\0" + raw + b"\0")
            data = json.loads(raw or b"{}")
            if not isinstance(data, dict):
                raise ValueError(f"{path}: expected an object of TYPE -> [patterns]")
            parsed[name] = {str(t).upper(): [re.compile(p) for p in pats]
                            for t, pats in data.items()}
        return cls(parsed["allow"], parsed["deny"], digest.hexdigest())

    def apply(self, text: str, detections: list[Entity]
              ) -> tuple[list[Entity], dict[str, int]]:
        """(refined detections, suppressed count per type). Allow removes a
        same-type detection whose value fullmatches; deny adds matches as
        ``list``-layer detections. Pure."""
        kept: list[Entity] = []
        suppressed: dict[str, int] = {}
        for e in detections:
            t = e.entity_type.upper()
            if any(p.fullmatch(e.text) for p in self.allow.get(t, ())):
                suppressed[t] = suppressed.get(t, 0) + 1
                continue
            kept.append(e)
        for t, pats in self.deny.items():
            for p in pats:
                for m in p.finditer(text):
                    kept.append(Entity(t, m.group(0), m.start(), m.end(), LIST_LAYER, 1.0))
        return kept, suppressed
