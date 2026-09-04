"""CLI: PII-detection evaluation over a gold JSONL corpus.

    python -m wordsworth.eval.pii_run gold.jsonl [--layers deterministic,openanonymiser] [--json]

Runs the deployed detection seam (deterministic detectors + the OpenAnonymiser
service at ``WORDSWORTH_OPENANONYMISER_URL``) over the gold texts and prints
precision/recall/F1 per type (span + token level), per layer, and the leak
count. Read-only; nothing is ingested, indexed or audited. A service failure is
a hard error, not an empty result."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..openanonymiser_driver import Entity, detect_entities
from .pii import deterministic_entities, evaluate_pii, load_gold

_LAYERS = {"deterministic": deterministic_entities, "openanonymiser": detect_entities}


def build_detect(layers: list[str]):
    fns = []
    for name in layers:
        if name not in _LAYERS:
            raise ValueError(f"unknown layer {name!r} (want: {', '.join(_LAYERS)})")
        fns.append(_LAYERS[name])

    def detect(text: str) -> list[Entity]:
        return [e for fn in fns for e in fn(text)]
    return detect


def format_report(report: dict) -> str:
    lines = [f"documents={report['documents']}  gold_entities={report['gold_entities']}  "
             f"leaks={report['leaks']}"]
    for level in ("span", "token"):
        o = report["overall"][level]
        lines.append(f"overall/{level}: P={o['precision']:.3f} R={o['recall']:.3f} "
                     f"F1={o['f1']:.3f}")
        for t, m in report[level].items():
            lines.append(f"  {t:<14} P={m['precision']:.3f} R={m['recall']:.3f} "
                         f"F1={m['f1']:.3f}  tp={m['tp']} fp={m['fp']} fn={m['fn']}")
    for layer, r in report.get("per_layer", {}).items():
        o = r["overall"]["span"]
        lines.append(f"layer {layer}: span P={o['precision']:.3f} R={o['recall']:.3f} "
                     f"F1={o['f1']:.3f}  leaks={r['leaks']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wordsworth.eval.pii_run")
    ap.add_argument("gold", help="gold JSONL: {id, text, entities:[{start,end,type}]}")
    ap.add_argument("--layers", default="deterministic,openanonymiser")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    docs = load_gold(Path(a.gold))
    report = evaluate_pii(docs, build_detect([s.strip() for s in a.layers.split(",")]))
    print(json.dumps(report, indent=2) if a.json else format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
