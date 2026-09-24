# SPDX-License-Identifier: MIT
"""Dossiers: the scope a search is asked to state (dossier-scope).

Searching everything by default means that forgetting the scope and having no
scope are the same thing. In a system that holds personal data the widest answer
must never be the one you get by not thinking, so a scope is asked for and
"everything" is an explicit choice.

Membership is a fact about a PAIR. Content-addressing decides what a document IS
— the same bytes are one document — so the same PDF delivered in two cases must
not become two documents and the second case must not overwrite the first. Both
memberships simply exist, and adding one that is already there changes nothing.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import dossier_events
from .models import Document, Dossier, DossierDocument

#: What a caller passes to say "every dossier". A word and not an empty value,
#: so that a scope left out by accident cannot be read as this.
ALL = "alle"


class DossierError(ValueError):
    """A scope that cannot be acted on."""


def ensure(session: Session, name: str) -> Dossier:
    """The dossier with this name, created if it does not exist yet.

    Lezen-dan-schrijven is hier een race, en een dure: `Dossier.name` is uniek,
    dus twee gelijktijdige ingests op een nieuwe naam laten er één blokkeren op
    de unieke index voor de hele duur van de ander — en in `_ingest_one` omspant
    die de complete straat voor dat document (extract, anonimiseer, embed,
    indexeer). Wachten tot dat klaar is levert dan alsnog een IntegrityError op,
    en die kwam als een 500 naar buiten.

    Het insert staat daarom in een savepoint. Botst hij, dan rolt alleen dat
    savepoint terug en lezen we wat de ander net heeft geschreven — de sessie
    eromheen blijft heel, want die draagt het halve werk van een document.
    """
    name = (name or "").strip()
    if not name:
        raise DossierError("a dossier needs a name")
    if name.lower() == ALL:
        raise DossierError(f"{ALL!r} is the word for every dossier, not a name")
    found = session.execute(
        select(Dossier).where(Dossier.name == name)).scalars().first()
    if found is not None:
        return found
    try:
        with session.begin_nested():
            created = Dossier(name=name)
            session.add(created)
            session.flush()
        return created
    except IntegrityError:
        # De ander was eerder. Dat is geen fout: we wilden dat het dossier
        # bestaat, en dat is nu zo.
        bestaand = session.execute(
            select(Dossier).where(Dossier.name == name)).scalars().first()
        if bestaand is None:
            raise
        return bestaand


def add(session: Session, dossier_id: UUID, document_id: UUID, *,
        actor: str, batch: str | None = None) -> bool:
    """Make this document a member. Returns whether it was not already one.

    Adding an existing membership is not an error: content already ingested
    being delivered into another case is normal. Same for a concurrent add —
    same savepoint, same reason as in `ensure`.

    `actor` has no default on purpose: a default would make the anonymous case
    the easy one, and arriving through ingest is an actor too. Why no reason is
    asked for: see `remove`, and `dossier_events` for both homes.
    """
    doc = session.get(Document, document_id)
    if doc is not None and doc.superseded_by is not None:
        # A retired copy has no business in a case: its survivor holds the
        # same bytes (one-document-per-object). Refused here, at the one place
        # every membership passes, rather than trusted to every caller.
        raise DossierError(f"document {document_id} is superseded by "
                           f"{doc.superseded_by}; add that one instead")
    existing = session.get(DossierDocument, (dossier_id, document_id))
    if existing is not None:
        return False
    try:
        with session.begin_nested():
            session.add(DossierDocument(dossier_id=dossier_id,
                                        document_id=document_id))
            session.flush()
    except IntegrityError:
        return False
    # Only after the membership exists: a record for a lost race would claim an
    # act that did not happen.
    dossier_events.membership_changed(
        session, document_id=document_id, dossier_id=dossier_id,
        dossier=dossier_events.name_of(session, dossier_id),
        step=dossier_events.ADDED,
        actor=actor, batch=batch)
    return True


def remove(session: Session, dossier_id: UUID, document_id: UUID, *,
           actor: str, reason: str, batch: str | None = None) -> bool:
    """Undo a membership. Returns whether there was one.

    Removing one that is not there is not an error, for the same reason adding
    an existing one is not: both are statements about a state.

    `reason` is required here while `add` asks for none, and that asymmetry is
    the point: an addition is visible in the result, a removal leaves nothing
    behind except what someone wrote down at the time.
    """
    if not (reason or "").strip():
        raise DossierError("removing a document from a dossier needs a reason")
    existing = session.get(DossierDocument, (dossier_id, document_id))
    if existing is None:
        return False
    naam = dossier_events.name_of(session, dossier_id)
    session.delete(existing)
    session.flush()
    dossier_events.membership_changed(
        session, document_id=document_id, dossier_id=dossier_id, dossier=naam,
        step=dossier_events.REMOVED, actor=actor, reason=reason, batch=batch)
    return True


def rename(session: Session, old: str, new: str, *, actor: str = "",
           lifecycle=None) -> Dossier:
    """Give a dossier another name. Moves no document.

    The identity is the dossier, not the word used for it — which is why this is
    safe and why a name can be corrected without touching what is in it.
    """
    found = session.execute(
        select(Dossier).where(Dossier.name == old.strip())).scalars().first()
    if found is None:
        raise DossierError(f"unknown dossier: {old}")
    new = (new or "").strip()
    if not new:
        raise DossierError("a dossier needs a name")
    if new.lower() == ALL:
        raise DossierError(f"{ALL!r} is the word for every dossier, not a name")
    clash = session.execute(
        select(Dossier).where(Dossier.name == new)).scalars().first()
    if clash is not None and clash.id != found.id:
        raise DossierError(f"a dossier named {new!r} already exists")
    oud = old.strip()
    found.name = new
    session.flush()
    # The dossier's own stream, not the documents': this moved none of them.
    dossier_events.renamed(session, lifecycle, dossier=found, old=oud, actor=actor)
    return found


def homeless(session: Session) -> int:
    """How many documents belong to no dossier at all.

    Invisible to every scoped search. Allowed mid-reclassification, counted
    always: this is the state in which a document is most easily lost, and the
    moment it happens is the moment someone can still act on it.
    """
    from .models import Document

    member = select(DossierDocument.document_id)
    return len(list(session.execute(
        select(Document.id).where(Document.id.not_in(member))).scalars()))


def documents_in(session: Session, dossier_ids: list[UUID]) -> set[UUID]:
    """Every document in any of these dossiers."""
    if not dossier_ids:
        return set()
    rows = session.execute(
        select(DossierDocument.document_id)
        .where(DossierDocument.dossier_id.in_(dossier_ids)))
    return {r[0] for r in rows}


def resolve(session: Session, scope: str | None) -> list[UUID] | None:
    """Turn a scope as a caller wrote it into dossier ids, or None for "all".

    A missing scope is an error and never "all": that is the whole point.
    """
    if scope is None or not str(scope).strip():
        raise DossierError("name a dossier, or 'alle' for every dossier")
    names = [n.strip() for n in str(scope).split(",") if n.strip()]
    if any(n.lower() == ALL for n in names):
        if len(names) > 1:
            raise DossierError(f"{ALL!r} cannot be combined with a name")
        return None
    found = list(session.execute(
        select(Dossier).where(Dossier.name.in_(names))).scalars())
    missing = sorted(set(names) - {d.name for d in found})
    if missing:
        raise DossierError(f"unknown dossier(s): {', '.join(missing)}")
    return [d.id for d in found]


def listing(session: Session) -> list[dict]:
    """Every dossier with how many documents it holds, newest first."""
    out = []
    for d in session.execute(
            select(Dossier).order_by(Dossier.created_at.desc())).scalars():
        count = len(documents_in(session, [d.id]))
        out.append({"id": str(d.id), "name": d.name, "documents": count})
    return out
