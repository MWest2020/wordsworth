# SPDX-License-Identifier: MIT
"""Samenvatten als commando, niet als script in de `args` van een Job
(samenvatten-als-commando).

Tot 2026-09-20 droeg de cluster-Job dit werk in zijn eigen `args`: een
`python -c` van dertig regels, met de hand aangemaakt en zichtbaar in geen
enkele repo. Een wijziging daarin is onnavolgbaar en na een herinstallatie is
hij weg — dezelfde fout als een realm dat alleen in een database bestaat. Dit
commando is dat script, nu een aanroepbaar `python -m wordsworth.samenvatten`
met een testbare `main()`.

De rekenkern verandert niet: `compute()` in `summaries.py` beslist wat er
gemaakt wordt, commit per document, en is idempotent. Dit bestand regelt
alleen de invoer (welke documenten) en de uitvoer (één regel, een exitcode).
"""
from __future__ import annotations

import argparse
import sys
import time
from uuid import UUID

from sqlalchemy import select

from . import dossiers
from .config import settings
from .db import make_engine, make_session_factory
from .generator import OllamaGenerator
from .models import Document, DocumentSummary
from .summaries import compute


def ontbrekend(session) -> list[UUID]:
    """Elk document dat nog geen samenvatting heeft, ongeacht dossier."""
    heeft_al = select(DocumentSummary.document_id)
    return [r[0] for r in session.execute(
        select(Document.id).where(Document.id.not_in(heeft_al)))]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m wordsworth.samenvatten",
        description="Maak samenvattingen: voor een of meer met de hand "
                    "opgegeven dossiers, of voor alles wat nog geen "
                    "samenvatting heeft.")
    keuze = ap.add_mutually_exclusive_group(required=True)
    keuze.add_argument("--dossier", action="append", type=UUID, metavar="UUID",
                       help="samenvatten voor dit dossier (herhaalbaar)")
    keuze.add_argument("--ontbrekend", action="store_true",
                       help="elk document dat nog geen samenvatting heeft")
    args = ap.parse_args(argv)

    engine = make_engine()
    session_factory = make_session_factory(engine)
    generator = OllamaGenerator.from_config()
    model = settings.llm_model

    begin = time.monotonic()
    with session_factory() as session:
        ids = sorted(dossiers.documents_in(session, args.dossier)) \
            if args.dossier else sorted(ontbrekend(session))
        uitkomst = compute(session, generator, ids, model=model)
        session.commit()
    duur = time.monotonic() - begin

    print(f"seen={uitkomst.seen} made={uitkomst.made} skipped={uitkomst.skipped} "
         f"failed={uitkomst.failed} without_text={uitkomst.without_text} "
         f"duur={duur:.1f}s", file=sys.stdout)
    return 1 if uitkomst.failed or uitkomst.without_text else 0


if __name__ == "__main__":     # pragma: no cover
    raise SystemExit(main())
