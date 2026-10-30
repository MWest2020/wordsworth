"""Over-detection baseline: how five ordinary Dutch words get typed today, and
what the current lists cost on a fixture corpus (redaction-overdetection).

Pure and offline: nothing here calls a network. Reachability and the real
service call live in ``overdetection_run`` (the CLI) — this module only holds
the fixture sentences and the report format, so the format can be proved by a
test without OpenAnonymiser running.

The label matters: this measures what detection would do NOW on given text,
not what a past run produced on different text (meting 05's pitfall). And
nothing here ever emits a detected value or a passage of document text —
counts and types only. ``word_counts`` is keyed by the five words named in the
proposal (not read out of any document), never by what a detector predicted.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..openanonymiser_driver import Entity
from .pii import GoldDoc, evaluate_pii

LABEL = "what detection would do now on this text"

WORDS = ["statushouders", "bewoners", "woningcorporaties", "juni",
         "wereldvluchtelingendag"]


def word_sentences() -> dict[str, str]:
    """One synthetic sentence per word — ordinary government-document Dutch,
    never the pilot corpus, no seeded PII."""
    return {
        "statushouders": "De gemeente biedt opvang aan statushouders in de regio.",
        "bewoners": "Bewoners van de straat ontvingen gisteren een brief van de gemeente.",
        "woningcorporaties": "Woningcorporaties bouwen dit jaar extra sociale huurwoningen.",
        "juni": "De raadsvergadering is gepland op een donderdag in juni.",
        "wereldvluchtelingendag": (
            "Op wereldvluchtelingendag organiseert de gemeente een bijeenkomst."),
    }


def word_counts(sentences: dict[str, str],
                 detect: Callable[[str], list[Entity]]
                 ) -> dict[str, dict[str, int]]:
    """word -> {type: count}: how predicted entities type each word today,
    measured on its own sentence with RAW detection (no lists — a list would
    suppress exactly the type a future allow entry needs to see, per
    design.md). A predicted span counts for a word when the word appears in it
    as a whole token. Counts only: the sentence and the predicted text never
    appear in the result, only the type label."""
    out: dict[str, dict[str, int]] = {}
    for word, text in sentences.items():
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        counts: dict[str, int] = {}
        for e in detect(text):
            if pattern.search(e.text):
                t = e.entity_type.upper()
                counts[t] = counts.get(t, 0) + 1
        out[word] = counts
    return out


def lists_comparison(docs: list[GoldDoc], without: Callable[[str], list[Entity]],
                      with_: Callable[[str], list[Entity]]) -> dict:
    """{"without": report, "with": report}: one `evaluate_pii` per side. Each
    side is its own detection pass over the same fixture corpus, under one code
    version — the before/after meting 05 proved is NOT across two runs, but
    this (two outcomes of ONE run, differing only in what sits behind it)."""
    return {"without": evaluate_pii(docs, without), "with": evaluate_pii(docs, with_)}


@dataclass
class Report:
    date: str
    comparison: dict
    word_counts: dict[str, dict[str, int]]


def build_report(docs: list[GoldDoc], sentences: dict[str, str],
                  without: Callable[[str], list[Entity]],
                  with_: Callable[[str], list[Entity]], date: str) -> Report:
    return Report(date, lists_comparison(docs, without, with_),
                  word_counts(sentences, without))


def _row(t: str, without: dict, with_: dict) -> str:
    o = without.get(t) or {"precision": 0.0, "recall": 0.0, "fp": 0}
    w = with_.get(t) or {"precision": 0.0, "recall": 0.0, "fp": 0}
    return (f"| {t} | {o['precision']:.3f} | {o['recall']:.3f} | {o['fp']} | "
            f"{w['precision']:.3f} | {w['recall']:.3f} | {w['fp']} |")


def format_report(report: Report | None) -> str:
    """The markdown body. ``report`` is None exactly when OpenAnonymiser was
    unreachable — that state is "not run", never a table (a deterministic-only
    table would look like a baseline and measure a different thing)."""
    if report is None:
        return f"**{LABEL}**\n\nnot run: OpenAnonymiser was unreachable.\n"
    without = report.comparison["without"]["span"]
    with_ = report.comparison["with"]["span"]
    lines = [f"**{LABEL}**", "", f"date: {report.date}", "",
              "| type | precisie zonder | recall zonder | fp zonder | "
              "precisie met | recall met | fp met |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for t in sorted(set(without) | set(with_)):
        lines.append(_row(t, without, with_))
    lines += ["",
              f"lekken zonder lijsten: {report.comparison['without']['leaks']}",
              f"lekken met lijsten: {report.comparison['with']['leaks']}",
              "", "| woord | telling per type |", "| --- | --- |"]
    for word in WORDS:
        counts = report.word_counts.get(word, {})
        cell = ", ".join(f"{t}={n}" for t, n in sorted(counts.items())) or "geen detectie"
        lines.append(f"| {word} | {cell} |")
    return "\n".join(lines) + "\n"
