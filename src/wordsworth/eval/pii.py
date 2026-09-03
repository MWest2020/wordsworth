"""PII-detection metrics over a gold corpus (add-pii-detection-eval).

Gold = JSONL, one document per line: ``{"id", "text", "entities": [{"start",
"end", "type"}]}`` (the de-facto NER span format). Predictions = the same
``Entity`` objects the pipeline's detection seam produces, so what is measured
is exactly what is deployed. Pure functions; no I/O except ``load_gold``.

Two granularities: **span** (exact start/end/type match) and **token** (a
whitespace token of a gold span counts as found when a same-type prediction
covers it — partial hits get partial credit). ``leaks`` = gold entities with no
overlapping prediction of ANY type: the number the index invariant cares about."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .. import detectors
from ..detection_stats import DETERMINISTIC
from ..openanonymiser_driver import Entity

_TOKEN_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class GoldSpan:
    start: int
    end: int
    type: str


@dataclass
class GoldDoc:
    id: str
    text: str
    entities: list[GoldSpan]


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def prf(self) -> dict[str, float]:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return {"precision": p, "recall": r, "f1": f,
                "tp": self.tp, "fp": self.fp, "fn": self.fn}


def load_gold(path: Path) -> list[GoldDoc]:
    """Parse + validate: spans in range, start < end, no overlap within a doc.
    A malformed line is a hard error (never a silently skipped document)."""
    docs: list[GoldDoc] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        raw = json.loads(line)
        text = raw["text"]
        spans = sorted((GoldSpan(int(e["start"]), int(e["end"]), str(e["type"]).upper())
                        for e in raw.get("entities", [])), key=lambda s: s.start)
        last = 0
        for sp in spans:
            if not 0 <= sp.start < sp.end <= len(text) or sp.start < last:
                raise ValueError(f"gold line {n} ({raw.get('id')}): bad/overlapping span "
                                 f"{sp.start}-{sp.end}")
            last = sp.end
        docs.append(GoldDoc(str(raw["id"]), text, spans))
    return docs


def deterministic_entities(text: str) -> list[Entity]:
    """The deterministic layer as ``Entity`` spans (BSN/IBAN/email, validated)."""
    out: list[Entity] = []
    for label, pattern, validate in detectors.DETECTORS:
        for m in pattern.finditer(text):
            if validate is None or validate(m.group(0)):
                out.append(Entity(label.upper(), m.group(0), m.start(), m.end(),
                                  DETERMINISTIC, 1.0))
    return out


def _tokens(text: str, start: int, end: int) -> list[tuple[int, int]]:
    return [(m.start() + start, m.end() + start)
            for m in _TOKEN_RE.finditer(text[start:end])]


def _covered(tok: tuple[int, int], spans: Iterable[tuple[int, int]]) -> bool:
    return any(s <= tok[0] and tok[1] <= e for s, e in spans)


def score_doc(doc: GoldDoc, preds: list[Entity]) -> dict:
    """Per-type span and token counts for one document, plus its leak count."""
    span: dict[str, Counts] = {}
    token: dict[str, Counts] = {}
    gold_by_type: dict[str, list[GoldSpan]] = {}
    for g in doc.entities:
        gold_by_type.setdefault(g.type, []).append(g)
    pred_by_type: dict[str, list[Entity]] = {}
    for p in preds:
        pred_by_type.setdefault(p.entity_type.upper(), []).append(p)

    for t in set(gold_by_type) | set(pred_by_type):
        gs = gold_by_type.get(t, [])
        ps = pred_by_type.get(t, [])
        gset = {(g.start, g.end) for g in gs}
        pset = {(p.start, p.end) for p in ps}
        sc = span.setdefault(t, Counts())
        sc.tp += len(gset & pset)
        sc.fp += len(pset - gset)
        sc.fn += len(gset - pset)
        tc = token.setdefault(t, Counts())
        for g in gs:
            for tok in _tokens(doc.text, g.start, g.end):
                if _covered(tok, pset):
                    tc.tp += 1
                else:
                    tc.fn += 1
        for p in ps:
            for tok in _tokens(doc.text, p.start, p.end):
                if not _covered(tok, gset):
                    tc.fp += 1

    all_pred = [(p.start, p.end) for p in preds]
    leaks = sum(1 for g in doc.entities
                if not any(s < g.end and g.start < e for s, e in all_pred))
    return {"span": span, "token": token, "leaks": leaks}


def _merge(into: dict[str, Counts], part: dict[str, Counts]) -> None:
    for t, c in part.items():
        cell = into.setdefault(t, Counts())
        cell.tp += c.tp
        cell.fp += c.fp
        cell.fn += c.fn


def _summarise(span: dict[str, Counts], token: dict[str, Counts], leaks: int) -> dict:
    overall_s, overall_t = Counts(), Counts()
    for c in span.values():
        overall_s.tp += c.tp; overall_s.fp += c.fp; overall_s.fn += c.fn
    for c in token.values():
        overall_t.tp += c.tp; overall_t.fp += c.fp; overall_t.fn += c.fn
    return {
        "span": {t: c.prf() for t, c in sorted(span.items())},
        "token": {t: c.prf() for t, c in sorted(token.items())},
        "overall": {"span": overall_s.prf(), "token": overall_t.prf()},
        "leaks": leaks,
    }


def evaluate_pii(docs: list[GoldDoc], detect: Callable[[str], list[Entity]]) -> dict:
    """Run ``detect`` over every gold text; aggregate per type, overall, and —
    when detections carry a layer — per layer (each layer scored alone)."""
    span: dict[str, Counts] = {}
    token: dict[str, Counts] = {}
    leaks = 0
    per_layer: dict[str, dict] = {}
    for doc in docs:
        preds = detect(doc.text)
        r = score_doc(doc, preds)
        _merge(span, r["span"]); _merge(token, r["token"]); leaks += r["leaks"]
        for layer in {p.layer for p in preds}:
            lr = score_doc(doc, [p for p in preds if p.layer == layer])
            acc = per_layer.setdefault(layer, {"span": {}, "token": {}, "leaks": 0})
            _merge(acc["span"], lr["span"]); _merge(acc["token"], lr["token"])
            acc["leaks"] += lr["leaks"]
    report = _summarise(span, token, leaks)
    report["documents"] = len(docs)
    report["gold_entities"] = sum(len(d.entities) for d in docs)
    report["per_layer"] = {l: _summarise(a["span"], a["token"], a["leaks"])
                           for l, a in sorted(per_layer.items())}
    return report
