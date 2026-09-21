# SPDX-License-Identifier: MIT
"""Meet de onderwerpindeling én wat hij met het zoeken doet (onderwerpen).

Twee getallen, want het zijn twee vragen en een goed antwoord op de ene zegt
niets over de andere:

1. **Klopt de indeling?** De berekende groepen naast het bekende onderwerp uit
   `gold.jsonl` — adjusted rand index en purity. Ze staan naast elkaar omdat
   purity te makkelijk hoog wordt (één groep per document geeft 1.0) en de ARI
   te makkelijk laag leest zonder iets ernaast.
2. **Helpt het bij het zoeken?** Dezelfde queries, één keer over het hele
   dossier en één keer binnen het onderwerp — met de bestaande metrieken.

**Vooraf opgeschreven, zodat het achteraf geen bewegend doel is:** de verwachting
is dat (2) niet of nauwelijks beweegt. Een scope die de juiste documenten bevat,
haalt bovenaan dezelfde documenten naar boven. Gaat (2) omláág, dan is de scope
te smal en klopt de indeling niet.

Het onderwerp wordt voor (2) gekozen zoals een mens het zou kiezen die het
júiste onderwerp aanklikt: het berekende onderwerp waar de meeste documenten van
dat bekende onderwerp in zitten. Dat meet het plafond en niet het gemiddelde, en
dat hoort erbij te staan.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..search_index import SearchIndex
from .adapters import _external_ids
from .collection import load_qrels, load_queries
from .harness import evaluate
from .metrics import adjusted_rand_index, purity

_METRICS = ("r_precision", "recall@10", "map", "ndcg@10")


def known_topics(gold: Path) -> dict[str, str]:
    """{extern document-id: bekend onderwerp} uit `gold.jsonl`."""
    truth: dict[str, str] = {}
    for line in gold.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("topic"):
            truth[row["id"]] = row["topic"]
    return truth


def computed_topics(index: SearchIndex, dossier: str) -> dict[str, str]:
    """{extern document-id: berekend onderwerp-id}, voor wat een onderwerp heeft.

    Documenten zonder onderwerp staan er niet in. Dat is geen verzwijgen: hoevéél
    er buiten vielen is een apart getal, en het als fout meetellen zou de
    indeling straffen voor iets dat al gerapporteerd wordt.
    """
    found: dict[str, str] = {}
    for doc in index.documents_in(dossier):
        if doc.topics and doc.object_key:
            found[doc.object_key] = sorted(doc.topics)[0]
    return found


def best_topic_per_query(truth: dict[str, str], found: dict[str, str],
                         queries: dict[str, str]) -> dict[str, str]:
    """Voor elke query het berekende onderwerp dat er het beste bij hoort.

    De query-id is `q-<onderwerp>`; dat is de koppeling met de bekende indeling.
    """
    per_bekend: dict[str, Counter] = defaultdict(Counter)
    for doc, bekend in truth.items():
        if doc in found:
            per_bekend[bekend][found[doc]] += 1
    gekozen = {}
    for qid, tekst in queries.items():
        bekend = qid[2:] if qid.startswith("q-") else qid
        if per_bekend.get(bekend):
            gekozen[tekst] = per_bekend[bekend].most_common(1)[0][0]
    return gekozen


def measure(index: SearchIndex, dossier: str, gold: Path, queries_path: Path,
            qrels_path: Path, k: int = 10) -> dict:
    """Beide metingen over één corpus, in één antwoord."""
    truth = known_topics(gold)
    found = computed_topics(index, dossier)
    queries = load_queries(queries_path)
    qrels = load_qrels(qrels_path)
    per_query = best_topic_per_query(truth, found, queries)

    def zonder(query: str) -> list[str]:
        return _external_ids(index.search(query, size=k))

    def met(query: str) -> list[str]:
        topic = per_query.get(query)
        if topic is None:
            # Geen onderwerp voor deze query: dan is dit dezelfde zoekopdracht
            # als zonder scope, en dát moet er staan in plaats van een gat.
            return zonder(query)
        return _external_ids(index.search(query, size=k, topic=topic))

    in_corpus = len([d for d in index.documents_in(dossier)])
    return {
        "grouping": {
            "adjusted_rand_index": round(adjusted_rand_index(truth, found), 4),
            "purity": round(purity(truth, found), 4),
            "documents_in_dossier": in_corpus,
            "with_a_topic": len(found),
            "known": len(truth),
        },
        "retrieval": {
            "unscoped": {m: round(v, 4) for m, v in
                         evaluate(zonder, queries, qrels, k)["aggregate"].items()
                         if m in _METRICS},
            "topic_scoped": {m: round(v, 4) for m, v in
                             evaluate(met, queries, qrels, k)["aggregate"].items()
                             if m in _METRICS},
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dossier", required=True, help="dossier-id (uuid)")
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--queries", type=Path, required=True)
    ap.add_argument("--qrels", type=Path, required=True)
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args(argv)

    from ..opensearch_index import OpenSearchIndex

    report = measure(OpenSearchIndex.from_config(), args.dossier, args.gold,
                     args.queries, args.qrels, args.k)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(main())
