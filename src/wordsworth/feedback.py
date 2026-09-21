# SPDX-License-Identifier: MIT
"""De meldingen bij elkaar (overdetectie).

Losse meldingen zijn geen signaal. "Vijf mensen vonden `[LOCATION:a1b2c3d4]`
onterecht" is er wel een, en dat is de lijst waar een mens doorheen loopt
voordat hij de allow-lijst aanpast.

**Dit scherm toont geen waarden.** Wie wil weten wélke naam achter een token
zit, gaat langs de gewone weg: een grant, een rol, een geauditeerde onthulling.
Een overzichtsscherm dat "even" de waarde erbij zet, is precies de tweede deur
die dit project nergens heeft — en het zou de deur zijn met het grootste bereik,
want hij toont ze allemaal tegelijk.

Een eerdere versie wilde erbij zetten of een melding al was opgevolgd — of de
allow-lijst die waarde inmiddels onderdrukt. Dat vraagt om ontsleutelen, en dan
loopt de waarde tóch door dit bestand, ook al komt hij niet in het antwoord.
Voor een scherm dat belooft er niet bij te kunnen, is dat de verkeerde kant op.
Wie de lijst aanpast, kijkt zelf of de regel er al staat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditRecord, Document

STAP = "detection_feedback"


@dataclass
class Melding:
    """Eén samengevoegde melding: hetzelfde token of hetzelfde type, vaker."""

    kind: str                      # fp | fn
    type: str
    token: str | None
    aantal: int = 0
    melders: set[str] = field(default_factory=set)
    documenten: set[UUID] = field(default_factory=set)
    laatst: datetime | None = None

    @property
    def sleutel(self) -> tuple:
        return (self.kind, self.type, self.token)


def verzamel(session: Session, limiet: int = 500) -> list[Melding]:
    """Alle meldingen, samengevoegd en op gewicht gesorteerd.

    Gewicht is het aantal **verschillende melders**, niet het aantal meldingen:
    één iemand die tien keer klikt is geen tien mensen. Daarna pas op aantal.
    """
    rijen = session.execute(
        select(AuditRecord.document_id, AuditRecord.payload, AuditRecord.ts)
        .where(AuditRecord.step == STAP)
        .order_by(AuditRecord.seq.desc()).limit(limiet)
    ).all()

    per: dict[tuple, Melding] = {}
    for document_id, payload, ts in rijen:
        payload = payload or {}
        m = Melding(kind=str(payload.get("kind", "")),
                    type=str(payload.get("type", "")),
                    token=payload.get("token"))
        bestaand = per.setdefault(m.sleutel, m)
        bestaand.aantal += 1
        bestaand.documenten.add(document_id)
        if payload.get("caller"):
            bestaand.melders.add(str(payload["caller"]))
        if bestaand.laatst is None or (ts and ts > bestaand.laatst):
            bestaand.laatst = ts
    return sorted(per.values(),
                  key=lambda m: (len(m.melders), m.aantal), reverse=True)


def documentnamen(session: Session, ids) -> dict[UUID, str]:
    """De bestandsnamen bij de document-ids, voor de doorklik."""
    ids = list(ids)
    if not ids:
        return {}
    rijen = session.execute(
        select(Document.id, Document.filename, Document.object_key)
        .where(Document.id.in_(ids))).all()
    return {i: (naam or key.split("/")[-1]) for i, naam, key in rijen}
