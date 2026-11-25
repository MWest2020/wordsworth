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

    `put` only buffers the row on the session; `write_pending` stores the
    buffer under the audit chain lock, in pseudonym order
    (`docs/reference/lock-order.md`). Rows inserted in text order, before the
    chain lock, made two runs minting the same values wait in a circle (#465,
    #504). `process` and `reanonymize` write through `pseudonym_registry.link`,
    any other caller calls `write_pending` itself, before its audit record.
    Nothing is written implicitly: a commit with rows still buffered raises
    `UnwrittenMappings`; the end of the transaction drops the buffer."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None:
        # The first `put` of a pseudonym wins (both encrypt the same value).
        # Inside a transaction, so the buffer ends with it (the listeners
        # below); begins one if none is open, no statement is sent.
        self._session.connection()
        self._session.info.setdefault(_PENDING, {}).setdefault(pseudonym, dict(
            pseudonym=pseudonym, ciphertext=ciphertext, nonce=nonce,
            key_id=key_id, norm_version=norm_version,
            created_at=datetime.now(timezone.utc)))

    def get(self, pseudonym: str) -> Mapping | None:
        row = self._session.get(PiiMapping, pseudonym)
        if row is not None:
            return Mapping(row.pseudonym, row.ciphertext, row.nonce, row.key_id,
                           row.norm_version)
        p = self._session.info.get(_PENDING, {}).get(pseudonym)
        return None if p is None else Mapping(
            pseudonym, p["ciphertext"], p["nonce"], p["key_id"], p["norm_version"])

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
    is stored. Refused inside a savepoint: rolling that back would take the
    stored rows and the chain lock with it, the buffer already emptied."""
    if session.in_nested_transaction():
        raise RuntimeError("mapping_store.write_pending inside a savepoint: "
                           "a rollback of it would drop the rows it stores")
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


class UnwrittenMappings(RuntimeError):
    """A transaction is committing while `put` rows are still buffered."""


@event.listens_for(Session, "before_commit")
def _nothing_buffered_at_commit(session: Session) -> None:
    """Refuse a commit that would lose a `put`: the caller forgot
    `write_pending`. Loud on purpose: nothing is written and no lock is
    taken here, so the lock order stays where the code shows it. Only the
    outermost commit: SQLAlchemy fires this for a savepoint release too."""
    if session.in_nested_transaction():
        return
    pending = session.info.get(_PENDING)
    if pending:
        raise UnwrittenMappings(
            f"{len(pending)} pii_mappings rows were put and never written; "
            "call mapping_store.write_pending(session) before the commit")


@event.listens_for(Session, "after_transaction_end")
def _drop_at_end(session: Session, transaction) -> None:
    """The buffer lives as long as the outermost transaction: a commit got
    here with nothing buffered (above), a rollback or a `close` stores
    nothing. A savepoint's end is not it -- `register_live` and
    `dossiers.add` roll one back on a lost race, and the puts made before
    it belong to the run that goes on."""
    if transaction.parent is None:
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
