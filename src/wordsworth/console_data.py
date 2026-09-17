# SPDX-License-Identifier: MIT
"""What the console pages need from the database (console-demo).

Kept out of ``console.py`` so the router stays a router. Everything here reads;
nothing here decides who may see it — that is the middleware's job for pages and
the grant's job for values.
"""
from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select

from .grants import ACTIVE
from .models import AuditRecord, DocumentPseudonym, GrantRecord

#: Terms offered on the search page. Examples, not a promise: whether one matches
#: depends on the corpus that happens to be loaded, and a term with no hits says
#: so rather than being quietly dropped.
SUGGESTED = ["vergunning", "woo-verzoek", "bezwaar", "subsidie", "handhaving",
             "besluit", "beslistermijn", "openbaarmaking"]

_WORD = re.compile(r"\w+", re.UNICODE)
_TOKEN = re.compile(r"\[([A-Z0-9_]+):([0-9a-f]{8})\]")


def fragment(text: str, query: str, width: int = 90) -> str:
    """A window of the PSEUDONYMISED text around the first matching word.

    From the stored text, never from a source document — the fragment is a
    quotation of what the index actually holds, and that is the whole point of
    showing it.
    """
    if not text:
        return ""
    words = [w.lower() for w in _WORD.findall(query or "")]
    at = -1
    for w in words:
        m = re.search(rf"\b{re.escape(w)}", text, re.IGNORECASE)
        if m:
            at = m.start()
            break
    if at < 0:                       # matched on something we cannot locate
        return text[:width * 2].strip().replace("\n", " ") + "…"
    start, end = max(0, at - width), min(len(text), at + width)
    out = text[start:end].strip().replace("\n", " ")
    return ("…" if start else "") + out + ("…" if end < len(text) else "")


def reveal_history(session, document_id: UUID) -> list[dict]:
    """The reveals recorded against this document: when, who, which grant, which
    types. Never a value — the payload holds type names only.

    ``requested`` and ``resolved`` are kept apart on purpose. The audit's
    ``types`` is what actually came back out of the mapping store; a request can
    name a type and resolve nothing (a token minted under a key this deployment
    no longer holds). Showing only one number makes "nothing resolved" look
    exactly like "nothing was asked for", and those are different events.
    """
    rows = session.execute(
        select(AuditRecord)
        .where(AuditRecord.document_id == document_id,
               AuditRecord.step == "deanonymize")
        .order_by(AuditRecord.seq.desc()).limit(25)).scalars()
    out = []
    for r in rows:
        p = r.payload or {}
        resolved = sorted(p.get("types") or [])
        requested = sorted(p.get("requested_types") or [])
        out.append({
            "ts": r.ts,
            "caller": p.get("caller") or p.get("actor") or "—",
            "grant": (p.get("grant_id") or "")[:8],
            "resolved": resolved,
            "requested": requested,
            # Asked for and not resolved: the interesting case, and the one a
            # single list hides.
            "unresolved": [t for t in requested if t not in resolved],
            "withheld": sorted(p.get("withheld_types") or []),
            "seq": r.seq,
        })
    return out


def grants_for(session, document_id: UUID) -> tuple[list[dict], int]:
    """The ACTIVE grants that apply to this document, and how many revoked ones
    also point at it.

    Active ones are listed whoever they belong to: a grant issued to someone else
    is exactly what makes the point — the screen offers it, the door refuses it.

    Revoked ones are counted, not listed. A revoked grant authorises nothing, so
    a row per piece of history buries the one grant that can actually be used;
    six dead ones from a test in August did exactly that. The count stays,
    because "revocable" is part of the claim and a screen that shows no trace of
    it quietly drops that half.
    """
    rows = list(session.execute(
        select(GrantRecord)
        .where((GrantRecord.document_id == document_id)
               | (GrantRecord.document_id.is_(None)))
        .order_by(GrantRecord.created_at.desc()).limit(50)).scalars())
    active = [{"grant_id": g.grant_id, "recipient": g.recipient,
               "types": sorted(g.allowed_types or []), "status": g.status,
               "expires_at": g.expires_at,
               "scope": "dit document" if g.document_id else "alle documenten"}
              for g in rows if g.status == ACTIVE]
    return active, sum(1 for g in rows if g.status != ACTIVE)


def token_types(session, document_id: UUID) -> dict[str, int]:
    """``{LABEL: count}`` for one document, from the registered pseudonyms."""
    out: dict[str, int] = {}
    for (token,) in session.execute(
            select(DocumentPseudonym.pseudonym)
            .where(DocumentPseudonym.document_id == document_id)):
        label = token[1:].split(":")[0].upper()
        out[label] = out.get(label, 0) + 1
    return out


def marked(text: str) -> list[dict]:
    """Split pseudonymised text into plain runs and typed tokens.

    Done here rather than in the template so the page never has to decide what
    is a token; the regex is the same shape the registry uses.
    """
    parts, at = [], 0
    for m in _TOKEN.finditer(text or ""):
        if m.start() > at:
            parts.append({"text": text[at:m.start()], "type": None})
        parts.append({"text": m.group(0), "type": m.group(1)})
        at = m.end()
    if at < len(text or ""):
        parts.append({"text": text[at:], "type": None})
    return parts


def label(doc) -> str:
    """What to call this document on screen.

    The name it arrived under when we have it. Otherwise "naamloos" with the
    first eight characters of the content hash — enough to tell two documents
    apart and honest about what it is. Printing the full hash as if it were a
    name is the thing this replaces: it answers "which document is this?" with
    a string nobody can hold in their head.
    """
    if doc is None:
        return "(document niet meer aanwezig)"
    if doc.filename:
        return doc.filename
    key = (doc.object_key or "").split("/")[-1]
    return f"naamloos ({key[:8]})" if key else "naamloos"


class _Missing:
    """An object_key for a hit whose document row is gone. The index can outlive
    a delete; showing the id beats rendering an empty cell."""
    object_key = "(document niet meer aanwezig)"
    filename = None


def types_per_document(session) -> dict:
    """``document_id -> {LABEL: count}`` from the registered pseudonyms."""
    rows = session.execute(select(DocumentPseudonym.document_id,
                                  DocumentPseudonym.pseudonym))
    out: dict = {}
    for doc_id, token in rows:
        label = token[1:].split(":")[0].upper()
        out.setdefault(doc_id, {})
        out[doc_id][label] = out[doc_id].get(label, 0) + 1
    return out


def reach(session, types: set[str]) -> tuple[int, list[str]]:
    """How many documents carry EVERY one of these types, and which of them the
    corpus cannot show at all.

    A type no detector emits occurs nowhere, and a bare 0 then reads as "does
    not occur" when the true answer is "cannot be seen". The screen has to say
    which, or the number quietly reassures.
    """
    wanted = {t.upper() for t in types}
    per_doc = types_per_document(session)
    seen = {lbl for present in per_doc.values() for lbl in present}
    return (sum(1 for present in per_doc.values() if wanted <= set(present)),
            sorted(wanted - seen))
