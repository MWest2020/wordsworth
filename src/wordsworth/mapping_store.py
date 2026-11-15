"""The separated encrypted mapping store (pseudonym -> ciphertext)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sqlalchemy import delete as sa_delete
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from . import audit
from .crypto import decrypt, encrypt
from .keys import KeyProvider
from .models import PiiMapping


@dataclass
class Mapping:
    pseudonym: str
    ciphertext: bytes
    nonce: bytes
    key_id: str
    norm_version: str | None = None  # normalisation profile; None = legacy (raw)


@runtime_checkable
class MappingStore(Protocol):
    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None: ...
    def get(self, pseudonym: str) -> Mapping | None: ...
    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int: ...


class PostgresMappingStore:
    """Separated store in PostgreSQL. `put` is idempotent: one row per pseudonym.

    `put` writes nothing yet: it buffers the row on the session, and
    `write_pending` stores the buffered rows under the audit chain lock, in
    pseudonym order (`docs/reference/lock-order.md`). An anonymizer calls
    `put` in the order values appear in a text, long before its run holds the
    chain lock; rows inserted then, uncommitted, made two runs minting the
    same new values wait for each other in a circle (#465, #504). `process`
    and `reanonymize` write through `pseudonym_registry.link`, the dataset
    run calls `write_pending` before its audit record; whatever is still
    buffered at commit is written then (`_write_at_commit`), so a `put` is
    never silently lost."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None:
        # The first `put` of a pseudonym wins, as the first row does in the
        # table: both encrypt the same value.
        # Inside a transaction, so the buffer ends with it: stored at its
        # commit at the latest, dropped at its rollback (the two listeners
        # below). Begins one if none is open; no statement is sent.
        self._session.connection()
        self._session.info.setdefault(_PENDING, {}).setdefault(pseudonym, dict(
            pseudonym=pseudonym, ciphertext=ciphertext, nonce=nonce,
            key_id=key_id, norm_version=norm_version,
            created_at=datetime.now(timezone.utc)))

    def get(self, pseudonym: str) -> Mapping | None:
        row = self._session.get(PiiMapping, pseudonym)
        if row is None:
            pending = self._session.info.get(_PENDING, {}).get(pseudonym)
            if pending is None:
                return None
            return Mapping(pseudonym, pending["ciphertext"], pending["nonce"],
                           pending["key_id"], pending["norm_version"])
        return Mapping(row.pseudonym, row.ciphertext, row.nonce, row.key_id,
                       row.norm_version)

    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int:
        """Re-encrypt every entry under ``old_id`` onto ``new_id`` and return the
        count. Decrypts with the old key, re-encrypts with the new (fresh nonce),
        and updates the row's ``key_id`` in place. Only ``pii_mappings`` is
        touched — documents and the index are never modified. This is the payoff
        of the separated store over in-document PII: rotation is cheap."""
        old = key_provider.key(old_id)
        new = key_provider.key(new_id)
        rows = self._session.execute(
            select(PiiMapping).where(PiiMapping.key_id == old_id)
        ).scalars().all()
        for row in rows:
            plaintext = decrypt(old.material, row.ciphertext, row.nonce)
            row.ciphertext, row.nonce = encrypt(new.material, plaintext)
            row.key_id = new_id
        self._session.flush()
        return len(rows)


#: `Session.info` key: the rows `put` buffered and `write_pending` has not
#: stored yet, by pseudonym. On the session, not on the store, because the
#: writer (`pseudonym_registry.link`) has the session and not the store the
#: anonymizer was built on. Emptied by every `write_pending`.
_PENDING = "pii_mappings_pending"


def write_pending(session: Session, only: set[str] | None = None) -> None:
    """Store the buffered mapping rows and hold them until the transaction
    ends. Under the audit chain lock, taken here (it flushes first), in
    pseudonym order: `INSERT ... ON CONFLICT DO NOTHING`, then FOR KEY SHARE.

    A deletion removes a mapping no document is linked to, and decides that
    under the same lock (`deletion_mappings`), so a row stored or found here
    cannot go before this transaction's links commit (#465). Every writer of
    `pii_mappings` being under the chain lock also means an insert here never
    waits for another transaction's uncommitted insert.

    ``only``: the pseudonyms the caller links (the tokens of the text it
    keeps). Buffered rows outside it are dropped, not stored -- nothing would
    refer to them; rows of ``only`` that were not buffered (another run
    minted them earlier) are only held. Without ``only`` everything buffered
    is stored."""
    pending = session.info.pop(_PENDING, {})
    names = sorted(pending if only is None else only)
    audit.lock_chain(session)
    if not names:
        return
    rows = [pending[name] for name in names if name in pending]
    if rows:
        session.execute(pg_insert(PiiMapping)
                        .on_conflict_do_nothing(index_elements=["pseudonym"]), rows)
    session.execute(select(PiiMapping.pseudonym)
                    .where(PiiMapping.pseudonym.in_(names))
                    .order_by(PiiMapping.pseudonym)
                    .with_for_update(key_share=True, read=True))


@event.listens_for(Session, "before_commit")
def _write_at_commit(session: Session) -> None:
    """The net under every `put`: rows still buffered when the transaction
    commits are stored first, the same way. A caller that appends an audit
    record after its `put`s holds the chain lock by then already."""
    if session.info.get(_PENDING):
        write_pending(session)


@event.listens_for(Session, "after_rollback")
def _drop_at_rollback(session: Session) -> None:
    """A rolled-back run stores nothing, its buffered rows included. (A
    savepoint rolling back is not this event.)"""
    session.info.pop(_PENDING, None)


def remove_orphans(session: Session, pseudonyms: list[str]) -> None:
    """Delete these mapping rows, locked FOR UPDATE in pseudonym order first.
    The caller holds the audit chain lock and has checked, under it, that no
    other document is linked to them (`deletion_mappings`)."""
    if not pseudonyms:
        return
    session.execute(select(PiiMapping.pseudonym)
                    .where(PiiMapping.pseudonym.in_(pseudonyms))
                    .order_by(PiiMapping.pseudonym).with_for_update())
    session.execute(sa_delete(PiiMapping)
                    .where(PiiMapping.pseudonym.in_(pseudonyms))
                    .execution_options(synchronize_session="fetch"))


class InMemoryMappingStore:
    """Dict-backed ``MappingStore`` — a test double and a non-DB wiring option,
    mirroring ``InMemoryIndex``. ``put`` is idempotent: one entry per pseudonym."""

    def __init__(self) -> None:
        self._d: dict[str, Mapping] = {}

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None:
        self._d.setdefault(
            pseudonym, Mapping(pseudonym, ciphertext, nonce, key_id, norm_version))

    def get(self, pseudonym: str) -> Mapping | None:
        return self._d.get(pseudonym)

    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int:
        old = key_provider.key(old_id)
        new = key_provider.key(new_id)
        n = 0
        for pseudonym, m in list(self._d.items()):
            if m.key_id != old_id:
                continue
            plaintext = decrypt(old.material, m.ciphertext, m.nonce)
            ciphertext, nonce = encrypt(new.material, plaintext)
            self._d[pseudonym] = Mapping(pseudonym, ciphertext, nonce, new_id,
                                         m.norm_version)
            n += 1
        return n
