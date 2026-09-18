# SPDX-License-Identifier: MIT
"""Dossiers: the scope a search has to state (dossier-scope)."""
import pytest
from sqlalchemy import select

from wordsworth import dossiers
from wordsworth.models import Document, DossierDocument
from wordsworth.pipeline import dossiers_of, ingest, register
from wordsworth.search_index import InMemoryIndex

PDF = b"%PDF-1.4 een besluit"
ANDER = b"%PDF-1.4 een ander besluit"


class Store:
    """Object store stand-in: ingest only needs put()."""

    def __init__(self):
        self.objects = {}

    def put(self, key, data):
        self.objects[key] = data


# --- membership ------------------------------------------------------------

def test_the_same_bytes_in_two_dossiers_stay_one_document(session):
    store = Store()
    a = ingest(session, store, PDF, dossier="zaak-a")
    b = ingest(session, store, PDF, dossier="zaak-b")
    session.commit()
    assert a.id == b.id
    assert len(session.execute(select(Document)).scalars().all()) == 1
    assert sorted(dossiers_of(session, a.id)) == sorted(
        str(d) for d in [dossiers.ensure(session, "zaak-a").id,
                         dossiers.ensure(session, "zaak-b").id])


def test_ingesting_into_the_same_dossier_twice_changes_nothing(session):
    store = Store()
    a = ingest(session, store, PDF, dossier="zaak-a")
    ingest(session, store, PDF, dossier="zaak-a")
    session.commit()
    rows = session.execute(select(DossierDocument).where(
        DossierDocument.document_id == a.id)).scalars().all()
    assert len(rows) == 1


def test_adding_an_existing_membership_reports_that_it_was_there(session):
    d = dossiers.ensure(session, "zaak")
    doc = register(session, "documents/aa")
    session.commit()
    assert dossiers.add(session, d.id, doc.id) is True
    assert dossiers.add(session, d.id, doc.id) is False


def test_a_dossier_needs_a_name(session):
    with pytest.raises(dossiers.DossierError):
        dossiers.ensure(session, "   ")


def test_the_word_for_everything_is_not_a_name(session):
    """Otherwise a dossier called 'alle' would make the scope unreadable."""
    with pytest.raises(dossiers.DossierError):
        dossiers.ensure(session, "alle")


# --- resolving a scope -----------------------------------------------------

def test_a_missing_scope_is_an_error_and_never_everything(session):
    """The whole promise: forgetting the scope must not give the widest answer."""
    for leeg in [None, "", "   "]:
        with pytest.raises(dossiers.DossierError):
            dossiers.resolve(session, leeg)


def test_everything_is_spelled_out(session):
    assert dossiers.resolve(session, "alle") is None
    assert dossiers.resolve(session, "ALLE") is None


def test_everything_cannot_be_combined_with_a_name(session):
    """'alle,zaak-a' is either a mistake or a misunderstanding; both deserve to
    be said out loud rather than resolved into one of the two meanings."""
    dossiers.ensure(session, "zaak-a")
    session.commit()
    with pytest.raises(dossiers.DossierError):
        dossiers.resolve(session, "alle,zaak-a")


def test_an_unknown_dossier_is_named_in_the_error(session):
    dossiers.ensure(session, "zaak-a")
    session.commit()
    with pytest.raises(dossiers.DossierError) as exc:
        dossiers.resolve(session, "zaak-a,verzonnen")
    assert "verzonnen" in str(exc.value) and "zaak-a" not in str(exc.value)


# --- the index -------------------------------------------------------------

def test_the_index_answers_only_from_the_dossiers_in_scope():
    index = InMemoryIndex()
    index.index("a", "vergunning hier", "ka", None, ["d1"])
    index.index("b", "vergunning elders", "kb", None, ["d2"])
    index.index("c", "vergunning in twee", "kc", None, ["d1", "d2"])
    assert {h.document_id for h in index.search("vergunning", only=["d1"])} == {"a", "c"}
    assert {h.document_id for h in index.search("vergunning", only=["d2"])} == {"b", "c"}
    assert {h.document_id for h in index.search("vergunning")} == {"a", "b", "c"}
    assert index.search("vergunning", only=["onbekend"]) == []


def test_a_document_in_two_dossiers_is_one_entry_in_the_index():
    index = InMemoryIndex()
    index.index("a", "tekst", "ka", None, ["d1", "d2"])
    assert len(index.search("tekst")) == 1
