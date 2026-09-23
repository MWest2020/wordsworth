"""SQLAlchemy models. ``documents`` holds no current_state column — the current
state is DERIVED from the latest audit record (audit table = single source of
truth). ``audit_records`` is append-only (enforced by a trigger, see db.py)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Index, Integer,
                        LargeBinary, String, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    # The name the file arrived under. A LABEL, not an identity: the content
    # hash in object_key stays what this document IS. Two uploads of the same
    # bytes under two names are one document, and it keeps the first name it
    # got — renaming a file does not make it a different document.
    #
    # Nullable because it is genuinely unknown for everything ingested before
    # this column existed. A screen that prints the hash where the name is
    # missing is presenting an identifier as a name; it has to say "naamloos".
    filename: Mapped[str | None] = mapped_column(String, nullable=True)


class AuditRecord(Base):
    __tablename__ = "audit_records"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    step: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # prev_hash UNIQUE enforces a single linear chain: two records cannot claim
    # the same predecessor, so a fork fails at insert time.
    prev_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class KeyLifecycleEvent(Base):
    """An authorisation fact with no document of its own (key-audit-in-postgres).

    Grants issued and revoked, roles changed, dossiers renamed, keys rotated.
    Until 2026-09-23 these went to a JSONL file in the api pod's /tmp -- an
    emptyDir, wiped on every restart -- so the trail was append-only and gone.

    Its own table and its own hash chain, not `audit_records`: that table's
    `document_id` is a NOT NULL foreign key and must stay one, and these events
    have no document by definition. Append-only by the same trigger.
    """

    __tablename__ = "key_lifecycle_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class DocumentText(Base):
    """Derived working data: the ANONYMIZED text only. Never clear PII, so it is
    mutable (not the append-only audit table) and holds nothing sensitive."""

    __tablename__ = "document_texts"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True
    )
    anonymized_text: Mapped[str] = mapped_column(String, nullable=False)


class DocumentPseudonym(Base):
    """Which pseudonyms belong to which document.

    The mapping store is global — lookup by pseudonym, not by document — because
    one value must yield one token everywhere, or pseudonymised text stops being
    searchable. The cost is that `_reveal` resolves any token it meets, whoever
    minted it.

    Neutralising tokens that arrive in supplied text closes the path an attacker
    can walk today, but that is one line of defence at one entrance. This table
    guards the exit instead: a token that is not registered here for the document
    being revealed does not resolve, no matter how it got into the text.

    `source` is load-bearing, not decoration. A row written by an anonymisation
    run is "minted"; a row written by a backfill that read already-stored text is
    "backfilled", because a backfill cannot tell whether a token was minted there
    or slipped in before the guard existed. An incident investigation should be
    able to see that difference instead of assuming it.
    """

    __tablename__ = "document_pseudonyms"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True
    )
    pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)  # minted | backfilled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PiiMapping(Base):
    """Separated encrypted mapping store: pseudonym -> AES-GCM ciphertext of the
    original PII. Holds only ciphertext, never clear PII, and never lives in the
    document. One row per pseudonym."""

    __tablename__ = "pii_mappings"

    pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    # Normalisation profile the token was derived under (add-value-normalisation);
    # NULL = legacy row derived from the raw value.
    norm_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GrantRecord(Base):
    """A reveal grant: authorization to deanonymize a set of PII types, optionally
    scoped to one document and/or an expiry. Shareable (issued to a recipient) and
    revocable (status flips to ``revoked``). Holds no key material and no clear
    PII — it is purely the authorization record the reveal path enforces."""

    __tablename__ = "grants"

    grant_id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    # upper-case PII types, e.g. ["PERSON", "EMAIL"]
    allowed_types: Mapped[list] = mapped_column(JSONB, nullable=False)
    # NULL document_id = a global grant (any document)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)  # active | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actor: Mapped[str] = mapped_column(String, nullable=False)
    # add-domain-keys: pseudonymisation domain; NULL = legacy = default domain.
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    # rollen: deze grant ontleent zijn types aan een rol. NULL = de grant draagt
    # zijn eigen lijst, zoals elke grant vóór deze kolom bestond.
    role: Mapped[str | None] = mapped_column(String, nullable=True)


class KeyVaultRecord(Base):
    """Durable envelope-wrapped data key (ADR-0002). Stores ONLY the OpenBao
    Transit-wrapped key material — never clear key bytes. One ``active`` row per
    scope (PII type); rotated-out versions are ``retired`` but stay resolvable by
    ``key_id`` so existing mappings keep decrypting."""

    __tablename__ = "key_vault"

    key_id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, nullable=False, index=True)
    wrapped_material: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # active | retired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # At most one active key per scope — the DB enforces the invariant so a
    # concurrent double-mint cannot leave two active rows (the loser gets an
    # IntegrityError, which the provider turns into a re-read of the winner).
    __table_args__ = (
        Index("uq_key_vault_active_scope", "scope", unique=True,
              postgresql_where=text("status = 'active'")),
    )


class DeclaredCombination(Base):
    """A set of PII types an operator judged to identify together, and why.

    Stored rather than kept in a profile file, because establishing this depends
    on the population and the context and is therefore the reader's judgement,
    not the developer's. A rule that lives only in a file a developer edits is
    established by nobody.

    ``types`` is the sorted set joined by ``+``: it is the identity of the
    declaration, so the same set cannot be recorded twice with two reasons.
    """

    __tablename__ = "declared_combinations"

    types: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    declared_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))


class Dossier(Base):
    """A named collection of documents: a case, a Woo request, a delivery.

    The thing search is scoped to. It has a name because a person picks it from a
    list, and an id because a name is not unique and a reference must be.
    """

    __tablename__ = "dossiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))


class DossierDocument(Base):
    """Which document belongs to which dossier.

    A table of its own and not a column on `documents`, because membership is a
    fact about a PAIR. Content-addressing says the same bytes are one document,
    so the same PDF delivered in two cases must not become two documents and the
    second case must not overwrite the first. Both memberships simply exist.

    The pair is the key, so adding the same one twice changes nothing — which is
    what makes re-ingesting a directory safe.
    """

    __tablename__ = "dossier_documents"

    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))


class Topic(Base):
    """Een onderwerp: een groep documenten binnen één dossier (onderwerpen).

    Alleen de beschrijving staat hier. Het lidmaatschap staat in de zoekindex,
    op het `topics`-veld van elk document — en daar alleen. Twee bronnen voor
    hetzelfde lidmaatschap is precies hoe antwoorden uit elkaar gaan lopen, en
    de scope die een zoekopdracht toepast kómt uit die index.

    `computed_name` is wat de berekening maakte, `given_name` wat een mens
    ervan vond. De eerste blijft staan als de tweede er is: waar een groep
    vandaan komt, blijft navertelbaar.
    """

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False, index=True)
    computed_name: Mapped[str] = mapped_column(String, nullable=False)
    given_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Waarover en wanneer gerekend is. Zonder deze twee leest een overzicht van
    # vier maanden oud als de huidige stand van het dossier.
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Role(Base):
    """Een rol: een naam plus de PII-types die eronder zichtbaar mogen zijn.

    Mark, 2026-09-19: *"ik maak een rol aan en selecteer welke PII's mogen, per
    document of globaal?"* — ja, met één scheiding. De **types** horen bij de
    rol; de **scope** (dit document of alles) hoort bij het toekennen, dus bij
    de grant. Zat de scope hier, dan waren "HR voor dit dossier" en "HR voor
    alles" twee rollen die morgen uit elkaar lopen.

    `active` is de breakglass. Een rol uitzetten werkt onmiddellijk en raakt
    geen enkele grant aan: `authorize()` lost de rol op bij het beslissen, dus
    een uitgezette rol levert een lege typeverzameling en elke grant die hem
    noemt autoriseert niets. Dat is de reden dat een rol een entiteit is en
    geen sjabloon — bij een sjabloon zou uitzetten betekenen dat je elke
    uitgegeven grant moet terugvinden, mét een tijdvenster, precies op het
    moment dat je er geen wilt.
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    #: Hoofdletter-PII-types, net als `grants.allowed_types`.
    allowed_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String, nullable=False)


class DocumentSummary(Base):
    """Een korte samenvatting van één document (samenvattingen).

    Hoort bij het document en niet bij de vraag: hem per zoekopdracht maken is
    traag én levert morgen een andere tekst op dezelfde vraag.

    `model` en `created_at` staan erbij omdat een samenvatting van llama3.2:3b
    een ander ding is dan een van een groter model, en een lezer moet kunnen
    zien welke er voor hem staat. Dat is geen administratie maar herkomst: dit
    is de enige tekst in dit systeem die niet terug te voeren is op iets dat is
    opgeslagen.
    """

    __tablename__ = "document_summaries"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))
