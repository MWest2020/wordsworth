# SPDX-License-Identifier: MIT
"""Rechtzetten wat verkeerd is ingedeeld (dossier-correctie).

Twee commando's, één regel eronder: **nooit raden.** Een indeling op grond van
een datum of een tekstpatroon is er een die niemand kan navertellen, en dan is
hij erger dan geen. Herkomst zegt waar een document vandaan komt omdat iets het
destijds heeft opgeschreven; al het andere is gevolgtrekking in dezelfde jas.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

from . import dossiers
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


def assign(session, mapping: dict[str, str], weg_uit: str | None = None) -> dict:
    """Zet elk document met een herkomstregel in het dossier van die herkomst."""
    bron = None
    if weg_uit:
        bron = session.execute(select(dossiers.Dossier).where(
            dossiers.Dossier.name == weg_uit)).scalars().first()
        if bron is None:
            raise dossiers.DossierError(f"unknown dossier: {weg_uit}")

    per_dossier: dict[str, int] = {}
    toegewezen = zonder_herkomst = 0
    for doc in session.execute(select(Document)).scalars():
        herkomst = mapping.get(doc.filename or "")
        if herkomst is None:
            zonder_herkomst += 1
            continue
        naam = naam_van(herkomst)
        doel = dossiers.ensure(session, naam)
        dossiers.add(session, doel.id, doc.id)
        if bron is not None:
            dossiers.remove(session, bron.id, doc.id)
        per_dossier[naam] = per_dossier.get(naam, 0) + 1
        toegewezen += 1
    return {"toegewezen": toegewezen, "zonder_herkomst": zonder_herkomst,
            "per_dossier": per_dossier, "nergens": dossiers.homeless(session)}


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
    args = ap.parse_args(argv)

    mapping = by_filename(args.herkomst, args.veld)
    print(f"herkomst: {len(mapping)} unieke bestandsnaam/namen", file=sys.stderr)
    with _sessie() as session:
        stats = assign(session, mapping, args.weg_uit)
        session.rollback() if args.dry_run else session.commit()
    kop = "zou indelen" if args.dry_run else "ingedeeld"
    print(f"{kop}: {stats['toegewezen']} document(en) in "
          f"{len(stats['per_dossier'])} dossier(s)")
    for naam, n in sorted(stats["per_dossier"].items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  {naam}")
    print(f"  zonder herkomstregel, niet aangeraakt: {stats['zonder_herkomst']}")
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
    args = ap.parse_args(argv)
    with _sessie() as session:
        d = dossiers.rename(session, args.oud, args.nieuw)
        aantal = len(dossiers.documents_in(session, [d.id]))
        session.commit()
    print(f"hernoemd: {args.oud!r} -> {args.nieuw!r} ({aantal} document(en) "
          f"onveranderd)")
    return 0
