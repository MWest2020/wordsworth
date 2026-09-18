"""Pure IR metric functions over a ranked list of doc ids + graded qrels.

Every function takes (ranked ids best-first, qrels-for-one-query) and returns a
float. No I/O, no state — unit-tested against hand-computed examples. Binary
metrics treat any relevance grade > 0 as relevant; NDCG uses the grade as gain.
No relevant docs (or, for NDCG, no ideal gain) -> 0.0 — never a NaN or a raise."""
from __future__ import annotations

from math import log2

Qrels = dict[str, int]  # doc_id -> graded relevance (0 = not relevant)


def _relevant(qrels: Qrels) -> set[str]:
    return {doc_id for doc_id, grade in qrels.items() if grade > 0}


def r_precision(ranked: list[str], qrels: Qrels) -> float:
    """|rel ∩ ranked[:R]| / R, where R is the number of relevant docs."""
    rel = _relevant(qrels)
    R = len(rel)
    if R == 0:
        return 0.0
    return sum(1 for doc_id in ranked[:R] if doc_id in rel) / R


def recall_at_k(ranked: list[str], qrels: Qrels, k: int = 10) -> float:
    """|rel ∩ ranked[:k]| / R."""
    rel = _relevant(qrels)
    R = len(rel)
    if R == 0:
        return 0.0
    return sum(1 for doc_id in ranked[:k] if doc_id in rel) / R


def average_precision(ranked: list[str], qrels: Qrels) -> float:
    """(1/R) * Σ_i [ranked[i]∈rel] * (hits so far / i), 1-indexed."""
    rel = _relevant(qrels)
    R = len(rel)
    if R == 0:
        return 0.0
    hits = 0
    total = 0.0
    for i, doc_id in enumerate(ranked, start=1):
        if doc_id in rel:
            hits += 1
            total += hits / i
    return total / R


def ndcg_at_k(ranked: list[str], qrels: Qrels, k: int = 10) -> float:
    """DCG@k / IDCG@k, gains taken from the graded qrels (0 for unjudged docs)."""

    def _dcg(gains: list[float]) -> float:
        return sum(g / log2(i + 1) for i, g in enumerate(gains, start=1))

    gains = [float(qrels.get(doc_id, 0)) for doc_id in ranked[:k]]
    ideal = sorted((float(g) for g in qrels.values()), reverse=True)[:k]
    idcg = _dcg(ideal)
    if idcg == 0:
        return 0.0
    return _dcg(gains) / idcg


def _pairs(n: int) -> int:
    return n * (n - 1) // 2


def adjusted_rand_index(truth: dict[str, str], found: dict[str, str]) -> float:
    """Hoe goed een berekende indeling overeenkomt met een bekende (onderwerpen).

    De Rand-index telt over alle paren documenten of twee indelingen het eens
    zijn: samen of niet samen. "Adjusted" trekt af wat toeval al oplevert —
    zonder die correctie scoort een indeling die alles in één groep gooit al
    hoog, en dat is precies de indeling die niets zegt.

    1.0 is gelijk, 0.0 is wat toeval zou doen, negatief is slechter dan toeval.
    Alleen documenten die in béíde indelingen voorkomen tellen mee: een document
    dat geen onderwerp kreeg is een ander getal (hoeveel er buiten vielen), en
    die twee door elkaar halen verbergt allebei.
    """
    from collections import Counter

    gedeeld = sorted(set(truth) & set(found))
    if len(gedeeld) < 2:
        return 0.0
    samen: Counter = Counter((truth[d], found[d]) for d in gedeeld)
    rijen: Counter = Counter(truth[d] for d in gedeeld)
    kolommen: Counter = Counter(found[d] for d in gedeeld)

    index = sum(_pairs(n) for n in samen.values())
    verwacht_rijen = sum(_pairs(n) for n in rijen.values())
    verwacht_kolommen = sum(_pairs(n) for n in kolommen.values())
    totaal = _pairs(len(gedeeld))
    verwacht = verwacht_rijen * verwacht_kolommen / totaal
    maximaal = (verwacht_rijen + verwacht_kolommen) / 2
    if maximaal == verwacht:
        return 1.0 if index == verwacht else 0.0
    return (index - verwacht) / (maximaal - verwacht)


def purity(truth: dict[str, str], found: dict[str, str]) -> float:
    """Het aandeel documenten dat in de meerderheid van zijn groep zit.

    Leesbaarder dan de ARI en makkelijker te misbruiken: één groep per document
    geeft purity 1.0. Daarom staan ze naast elkaar en nooit alleen.
    """
    from collections import Counter, defaultdict

    gedeeld = sorted(set(truth) & set(found))
    if not gedeeld:
        return 0.0
    groepen: dict[str, Counter] = defaultdict(Counter)
    for doc in gedeeld:
        groepen[found[doc]][truth[doc]] += 1
    return sum(max(c.values()) for c in groepen.values()) / len(gedeeld)
