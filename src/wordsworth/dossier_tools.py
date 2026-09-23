# SPDX-License-Identifier: MIT
"""Rechtzetten wat verkeerd is ingedeeld (dossier-correctie).

Twee commando's, één regel eronder: **nooit raden.** Een indeling op grond van
een datum of een tekstpatroon is er een die niemand kan navertellen, en dan is
hij erger dan geen. Herkomst zegt waar een document vandaan komt omdat iets het
destijds heeft opgeschreven; al het andere is gevolgtrekking in dezelfde jas.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from . import dossiers
from .key_audit_pg import PostgresKeyLifecycleAudit
from .db import make_engine, make_session_factory
from .models import Document


def by_filename(herkomst: Path, veld: str = "besluit") -> dict[str, str]:
    """``bestandsnaam -> herkomst`` uit een JSONL-bestand.

    Regels mogen dubbel staan — het herkomstbestand van de fetcher wordt met
    `append` geopend, dus twee keer draaien dupliceert alles. Dat is geen fout in
    de gegevens (documenten zijn content-geadresseerd) maar wel een reden om
    hier op naam te ontdubbelen in plaats van te tellen.
    """
    out: dict[str, str] = {}
    for regel in herkomst.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel.startswith("{"):
            continue
        rij = json.loads(regel)
        if rij.get("bestand") and rij.get(veld):
            out[rij["bestand"]] = rij[veld]
    return out


def naam_van(herkomst: str) -> str:
    """Een leesbare dossiernaam uit een herkomst-URL.

    De slug van de besluitpagina is al door een mens geschreven; er hoeft alleen
    een zaaknummer af en streepjes uit.
    """
    slug = herkomst.rstrip("/").rsplit("/", 1)[-1]
    import re

    slug = re.sub(r"\d{4}-\d{6}$", "", slug)
    return slug.replace("-", " ").strip()


def assign(session, mapping: dict[str, str], weg_uit: str | None = None,
           *, actor: str = "dossier-uit-herkomst",
           index=None) -> dict:
    """Zet elk document met een herkomstregel in het dossier van die herkomst.

    De index moet mee. Het dossier zit per document IN de index, dus een
    lidmaatschap verplaatsen in de database alleen laat een zoekopdracht op het
    nieuwe dossier niets vinden en op het oude nog wél — precies het scenario
    dat de spec belooft en dat de eerste versie hiervan niet bouwde. Op
    2026-09-18 moest dat met de hand worden rechtgezet.

    Alleen het dossierveld, nooit het hele document: dat laatste wist de
    embedding van wie `vector=` vergeet.
    """
    bron = None
    if weg_uit:
        bron = session.execute(select(dossiers.Dossier).where(
            dossiers.Dossier.name == weg_uit)).scalars().first()
        if bron is None:
            raise dossiers.DossierError(f"unknown dossier: {weg_uit}")

    # One command, one batch: the records stay per document (each really did
    # move) but a reader can see they were a single act.
    batch = uuid4().hex[:12]
    per_dossier: dict[str, int] = {}
    toegewezen = zonder_herkomst = 0
    for doc in session.execute(select(Document)).scalars():
        herkomst = mapping.get(doc.filename or "")
        if herkomst is None:
            zonder_herkomst += 1
            continue
        naam = naam_van(herkomst)
        doel = dossiers.ensure(session, naam)
        dossiers.add(session, doel.id, doc.id, actor=actor, batch=batch)
        if bron is not None:
            # The reason is the command itself: this document was assigned to
            # another dossier by its origin, so leaving the old one is not a
            # separate decision but the other half of the same one.
            dossiers.remove(session, bron.id, doc.id, actor=actor, batch=batch,
                            reason=f"moved to {naam} by origin")
        if index is not None:
            index.set_dossiers(str(doc.id), [str(d) for d in _dossier_ids(session, doc.id)])
        per_dossier[naam] = per_dossier.get(naam, 0) + 1
        toegewezen += 1
    return {"toegewezen": toegewezen, "zonder_herkomst": zonder_herkomst,
            "per_dossier": per_dossier, "nergens": dossiers.homeless(session)}


def _dossier_ids(session, document_id):
    from .models import DossierDocument

    return [r[0] for r in session.execute(
        select(DossierDocument.dossier_id).where(
            DossierDocument.document_id == document_id))]


def _sessie():
    return make_session_factory(make_engine())()


def main_assign(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-dossier-uit-herkomst",
        description="Deel documenten in op vastgelegde herkomst, niet op een gok")
    ap.add_argument("herkomst", type=Path, help="JSONL met bestand + herkomst")
    ap.add_argument("--veld", default="besluit", help="herkomstveld (standaard: besluit)")
    ap.add_argument("--weg-uit", help="dossier waar ze uit mogen zodra ze elders staan")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-index", action="store_true",
                    help="sla het bijwerken van de zoekindex over")
    args = ap.parse_args(argv)

    index = None
    if args.dry_run:
        print("droge run: de index wordt NIET aangeraakt", file=sys.stderr)
    elif not args.no_index:
        from .opensearch_index import OpenSearchIndex
        index = OpenSearchIndex.from_config()
        index.ensure_ready()

    mapping = by_filename(args.herkomst, args.veld)
    print(f"herkomst: {len(mapping)} unieke bestandsnaam/namen", file=sys.stderr)
    with _sessie() as session:
        stats = assign(session, mapping, args.weg_uit, index)
        session.rollback() if args.dry_run else session.commit()
    kop = "zou indelen" if args.dry_run else "ingedeeld"
    print(f"{kop}: {stats['toegewezen']} document(en) in "
          f"{len(stats['per_dossier'])} dossier(s)")
    for naam, n in sorted(stats["per_dossier"].items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  {naam}")
    print(f"  zonder herkomstregel, niet aangeraakt: {stats['zonder_herkomst']}")
    if index is None and stats["toegewezen"]:
        print("  LET OP: de index is niet bijgewerkt; tot een herindexering "
              "vindt een gescopete zoekopdracht deze documenten niet")
    if stats["nergens"]:
        print(f"  LET OP: {stats['nergens']} document(en) horen nu nergens bij en "
              f"zijn onvindbaar voor elke gescopete zoekopdracht")
    return 0


def main_rename(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-dossier-hernoem",
        description="Geef een dossier een andere naam; verplaatst geen document")
    ap.add_argument("oud")
    ap.add_argument("nieuw")
    # Who did it. Until 2026-09-23 this path recorded nothing at all -- not even
    # an anonymous event -- so "who renamed this" had no answer.
    ap.add_argument("--actor", default=f"cli:{getpass.getuser()}",
                    help="wie de hernoeming uitvoert (default: cli:<gebruiker>)")
    args = ap.parse_args(argv)
    with _sessie() as session:
        # The stream in THIS session: the rename and its record commit together.
        d = dossiers.rename(session, args.oud, args.nieuw, actor=args.actor,
                            lifecycle=PostgresKeyLifecycleAudit(session))
        aantal = len(dossiers.documents_in(session, [d.id]))
        session.commit()
    print(f"hernoemd: {args.oud!r} -> {args.nieuw!r} ({aantal} document(en) "
          f"onveranderd)")
    return 0
