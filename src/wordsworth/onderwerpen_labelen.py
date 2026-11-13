# SPDX-License-Identifier: MIT
"""`python -m wordsworth.onderwerpen_labelen --dossier <naam>`: label de
onderwerpen van één dossier (topic-labels-llm).

Een commando en geen verzoek, om dezelfde reden als `samenvatten`: één label
is ongeveer twee minuten modeltijd, en de zeventien onderwerpen van het
Gooise Meren-dossier zijn er vijfendertig. Dat past in geen HTTP-verzoek.

`--dossier` neemt de NAAM van het dossier, zoals de console, en niet de uuid
die `samenvatten --dossier` vraagt: wie dit bij de generale repetitie draait,
kent de naam. Standaard alleen de onderwerpen zonder label; `--opnieuw` doet
ze allemaal. Eén regel uitvoer, en een exitcode die niet nul is bij een
mislukte modelaanroep, een onbereikbare index of een onbekend dossier.
"""
from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import select

from .db import make_engine, make_session_factory
from .generator import OllamaGenerator
from .models import Dossier
from .search_index import SearchUnavailable
from .topic_labels import label_topics


def _index():
    from .opensearch_index import OpenSearchIndex

    return OpenSearchIndex.from_config()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m wordsworth.onderwerpen_labelen",
        description="Laat het taalmodel in het cluster de onderwerpen van één "
                    "dossier een label en één zin uitleg geven.")
    ap.add_argument("--dossier", required=True, metavar="NAAM",
                    help="de naam van het dossier, zoals de console hem toont")
    ap.add_argument("--opnieuw", action="store_true",
                    help="ook onderwerpen die al een label hebben")
    args = ap.parse_args(argv)

    session_factory = make_session_factory(make_engine())
    generator = OllamaGenerator.from_config()
    index = _index()

    begin = time.monotonic()
    with session_factory() as session:
        dossier_id = session.execute(
            select(Dossier.id).where(Dossier.name == args.dossier)).scalar()
        if dossier_id is None:
            print(f"dossier {args.dossier!r} bestaat niet", file=sys.stderr)
            return 1
        try:
            uit = label_topics(session, index, dossier_id, generator,
                               again=args.opnieuw)
        except SearchUnavailable as exc:
            print(f"de zoekindex is onbereikbaar; er is niets gelabeld ({exc})",
                  file=sys.stderr)
            return 1
        session.commit()
    duur = time.monotonic() - begin

    print(f"seen={uit.seen} labelled={uit.labelled} rejected={uit.rejected} "
          f"no_summaries={uit.no_summaries} skipped={uit.skipped} "
          f"failed={uit.failed} model={generator.model} duur={duur:.1f}s",
          file=sys.stdout)
    return 1 if uit.failed else 0


if __name__ == "__main__":     # pragma: no cover
    raise SystemExit(main())
