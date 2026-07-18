"""Separate append-only key-lifecycle audit stream.

Key rotations are *global* key-management facts with no document, so they do
not belong in the document hash-chain (that table is the document state
machine — a phantom "system document" would pollute it). Rotation events get
their own append-only stream instead, behind a driver seam.

The included driver reuses zeef's audit-JSONL (``zeef.audit.AuditLog``,
EUPL-1.2): one JSON event per line, append-only, never rewritten. Events carry
key *ids*, a re-encryption count, and the actor — never key material."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from zeef.audit import AuditLog

STREAM = "key_lifecycle"
ROTATION_ACTION = "key_rotation"


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
    ) -> None:
        self._log.event(
            STREAM,
            ROTATION_ACTION,
            old_key_id=old_key_id,
            new_key_id=new_key_id,
            entries_reencrypted=entries_reencrypted,
            actor=actor,
        )

    def events(self) -> list[dict[str, Any]]:
        """Read the stream back (verification/audit review)."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
