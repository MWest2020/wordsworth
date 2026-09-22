"""Separate append-only key-lifecycle audit stream.

Key rotations are *global* key-management facts with no document, so they do
not belong in the document hash-chain (that table is the document state
machine — a phantom "system document" would pollute it). Rotation events get
their own append-only stream instead, behind a driver seam.

The included driver reuses zeef's audit-JSONL (``zeef.audit.AuditLog``,
MIT): one JSON event per line, append-only, never rewritten. Events carry
key *ids*, a re-encryption count, and the actor — never key material."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from zeef.audit import AuditLog

STREAM = "key_lifecycle"
ROTATION_ACTION = "key_rotation"
GRANT_ISSUED_ACTION = "grant_issued"
GRANT_REVOKED_ACTION = "grant_revoked"
#: rollen: een rol aanmaken, inperken, uitzetten of weer aanzetten. Hier en niet
#: in de document-hashketen, om dezelfde reden als een sleutelrotatie en een
#: grant: een rol is een globaal autorisatiefeit zonder document. Eén rol raakt
#: duizend documenten, en een record per document zou de keten volschrijven met
#: duizend kopieën van hetzelfde feit.
ROLE_ACTION = "role_changed"
#: dossiers: hernoemen. Een hernoeming verplaatst geen document en verandert geen
#: lidmaatschap -- hij verandert een etiket dat duizend documenten delen. Daarom
#: hier en niet in de document-hashketen, om exact dezelfde reden als een rol.
#: Lidmaatschappen zelf horen wel op het document: zie `dossier_events.py`.
DOSSIER_RENAMED_ACTION = "dossier_renamed"


@runtime_checkable
class KeyLifecycleAudit(Protocol):
    """Driver contract for the key-lifecycle audit stream."""

    def rotation(
        self,
        *,
        old_key_id: str,
        new_key_id: str,
        entries_reencrypted: int,
        actor: str,
        scope: str | None = None,
    ) -> None: ...

    def grant_issued(
        self,
        *,
        grant_id: str,
        recipient: str,
        allowed_types: list[str],
        document_id: str | None,
        actor: str,
        domain: str | None = None,
        #: rollen: de rol waaraan deze grant zijn types ontleent, of None.
        role: str | None = None,
    ) -> None: ...

    def grant_revoked(self, *, grant_id: str, actor: str) -> None: ...

    def dossier_renamed(
        self,
        *,
        dossier_id: str,
        old: str,
        new: str,
        #: hoeveel documenten het dossier op dat moment hield -- hoe ver de
        #: wijziging reikte, zonder het per document weg te schrijven.
        documents: int,
        actor: str,
    ) -> None: ...

    def role_changed(
        self,
        *,
        role: str,
        change: str,          # created | types | deactivated | activated
        allowed_types: list[str],
        active: bool,
        actor: str,
        reason: str | None = None,
    ) -> None: ...


class JsonlKeyLifecycleAudit:
    """Append-only JSONL stream (reused zeef audit pattern)."""

    def __init__(self, path: Path) -> None:
        self._log = AuditLog(path)
        self.path = self._log.path

    def rotation(
        self,
        *,
        old_key_id: str,
        new_key_id: str,
        entries_reencrypted: int,
        actor: str,
        scope: str | None = None,
    ) -> None:
        self._log.event(
            STREAM,
            ROTATION_ACTION,
            old_key_id=old_key_id,
            scope=scope,
            new_key_id=new_key_id,
            entries_reencrypted=entries_reencrypted,
            actor=actor,
        )

    def grant_issued(
        self,
        *,
        grant_id: str,
        recipient: str,
        allowed_types: list[str],
        document_id: str | None,
        actor: str,
        domain: str | None = None,
        role: str | None = None,
    ) -> None:
        self._log.event(
            STREAM,
            GRANT_ISSUED_ACTION,
            grant_id=grant_id,
            domain=domain,
            recipient=recipient,
            allowed_types=allowed_types,
            document_id=document_id,
            actor=actor,
            role=role,
        )

    def grant_revoked(self, *, grant_id: str, actor: str) -> None:
        self._log.event(STREAM, GRANT_REVOKED_ACTION, grant_id=grant_id, actor=actor)

    def role_changed(self, *, role, change, allowed_types, active, actor,
                     reason=None) -> None:
        """Wat er met een rol gebeurde, wie het deed en waarom.

        De reden staat erin omdat een noodrem zonder reden een storing is die
        niemand achteraf kan uitleggen. Over een jaar is de enige manier om te
        beoordelen of het terecht was, weten waarvóór het was.

        `allowed_types` en `active` zijn de stand ná de wijziging: zo is uit de
        stream zelf te reconstrueren wat een rol op enig moment toestond,
        zonder de huidige tabel te hoeven geloven.
        """
        self._log.event(
            STREAM, ROLE_ACTION,
            role=role, change=change, allowed_types=list(allowed_types),
            active=active, actor=actor, reason=reason,
        )

    def dossier_renamed(self, *, dossier_id, old, new, documents, actor) -> None:
        """Hoe een dossier ging heten, en hoe ver dat reikte.

        `documents` is de reden dat dit record bestaat: het zegt hoeveel
        documenten deze ene handeling raakte, zonder duizend keer hetzelfde feit
        in de document-keten te schrijven.

        Oud EN nieuw staan erin, want een naam is waar een mens een dossier aan
        herkent. Alleen de nieuwe naam bewaren maakt een verwijzing in een oud
        rapport onvindbaar.
        """
        self._log.event(
            STREAM, DOSSIER_RENAMED_ACTION,
            dossier_id=dossier_id, old=old, new=new,
            documents=documents, actor=actor,
        )

    def events(self) -> list[dict[str, Any]]:
        """Read the stream back (verification/audit review)."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
