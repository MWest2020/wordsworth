"""CLI: the over-detection baseline against the deployed detection seam.

    python -m wordsworth.eval.overdetection_run gold.jsonl [--lists DIR] [--out PATH]

Needs OpenAnonymiser (``WORDSWORTH_OPENANONYMISER_URL``). Unreachable is
reported as "not run", never silently as a deterministic-only baseline — see
``overdetection.py`` and the change's ``design.md``. This is the live-run step:
Mark or the coding session runs it; the build does not."""
from __future__ import annotations

import argparse
import sys
from datetime import date as _date
from pathlib import Path

import httpx

from ..config import settings
from ..detection_lists import DetectionLists
from ..openanonymiser_driver import Entity, detect_entities
from .overdetection import build_report, format_report, word_sentences
from .pii import deterministic_entities, load_gold


def reachable(timeout: float = 5.0) -> bool:
    """A lightweight health probe, separate from the anonymize call itself.

    This diagnostic treats "cannot reach the service" as "not run" rather than
    raising — the one place in this system a connectivity failure is reported
    instead of raised, because that is the documented behaviour of THIS
    measurement, not of the pipeline (which stays fail-hard)."""
    url = settings.openanonymiser_url.rstrip("/") + "/api/v1/health"
    try:
        httpx.get(url, timeout=timeout).raise_for_status()
        return True
    except Exception:
        return False


def _detect(text: str) -> list[Entity]:
    return deterministic_entities(text) + detect_entities(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wordsworth.eval.overdetection_run")
    ap.add_argument("gold", help="gold JSONL for the precision/recall/leaks/fp table")
    ap.add_argument("--lists", default="lists", help="allow/deny lists directory")
    ap.add_argument("--out", default="docs/explanation/meting-overdetectie-07.md")
    a = ap.parse_args(argv)

    report = None
    if reachable():
        docs = load_gold(Path(a.gold))
        lijsten = DetectionLists.load(a.lists)

        def with_lists(text: str) -> list[Entity]:
            return lijsten.apply(text, _detect(text))[0]

        report = build_report(docs, word_sentences(), _detect, with_lists,
                               date=_date.today().isoformat())
    out = format_report(report)
    Path(a.out).write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
