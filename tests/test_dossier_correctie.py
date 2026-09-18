# SPDX-License-Identifier: MIT
"""Rechtzetten wat verkeerd is ingedeeld (dossier-correctie)."""
import json

import pytest

from wordsworth import dossiers
from wordsworth.dossier_tools import assign, by_filename, naam_van
from wordsworth.pipeline import dossiers_of, register

BESLUIT = ("https://open.gelderland.nl/woo-documenten/"
           "aanvullend-woo-besluit-over-omgevallen-boom-in-winterswijk2026-002818")


# --- removing and renaming -------------------------------------------------

def test_a_membership_can_be_undone(session):
    d = dossiers.ensure(session, "zaak")
    doc = register(session, "documents/aa")
    session.commit()
    dossiers.add(session, d.id, doc.id)
    assert dossiers.remove(session, d.id, doc.id) is True
    assert dossiers_of(session, doc.id) == []


def test_removing_one_that_is_not_there_is_not_an_error(session):
    """Both adding an existing one and removing an absent one are statements
    about a state, and the state is what matters."""
    d = dossiers.ensure(session, "zaak")
    doc = register(session, "documents/aa")
    session.commit()
    assert dossiers.remove(session, d.id, doc.id) is False


def test_renaming_moves_no_document(session):
    d = dossiers.ensure(session, "corpus-2026-09")
    doc = register(session, "documents/aa")
    session.commit()
    dossiers.add(session, d.id, doc.id)
    hernoemd = dossiers.rename(session, "corpus-2026-09", "Gooise Meren Woo-publicatie 2022")
    session.commit()
    assert hernoemd.id == d.id
    assert dossiers_of(session, doc.id) == [str(d.id)]
    assert dossiers.resolve(session, "Gooise Meren Woo-publicatie 2022") == [d.id]


def test_renaming_onto_an_existing_name_is_refused(session):
    dossiers.ensure(session, "een")
    dossiers.ensure(session, "twee")
    session.commit()
    with pytest.raises(dossiers.DossierError, match="already exists"):
        dossiers.rename(session, "een", "twee")


def test_renaming_an_unknown_dossier_is_refused(session):
    with pytest.raises(dossiers.DossierError, match="unknown"):
        dossiers.rename(session, "bestaat-niet", "iets")


def test_a_dossier_cannot_be_renamed_to_the_word_for_everything(session):
    dossiers.ensure(session, "zaak")
    session.commit()
    with pytest.raises(dossiers.DossierError):
        dossiers.rename(session, "zaak", "alle")


# --- documents that belong nowhere -----------------------------------------

def test_documents_belonging_nowhere_are_counted(session):
    """Invisible to every scoped search. Allowed mid-reclassification, counted
    always — this is where a document is most easily lost."""
    d = dossiers.ensure(session, "zaak")
    a = register(session, "documents/aa")
    b = register(session, "documents/bb")
    session.commit()
    dossiers.add(session, d.id, a.id)
    assert dossiers.homeless(session) == 1          # b
    dossiers.remove(session, d.id, a.id)
    assert dossiers.homeless(session) == 2


# --- assigning from provenance ---------------------------------------------

def test_a_readable_name_comes_out_of_the_slug():
    assert naam_van(BESLUIT) == ("aanvullend woo besluit over omgevallen boom "
                                 "in winterswijk")


def test_provenance_is_deduplicated_by_filename(tmp_path):
    """The fetcher opens its provenance file with `append`, so running it twice
    duplicates every line. Not a fault in the data — documents are
    content-addressed — but a reason to key on the name."""
    p = tmp_path / "herkomst.jsonl"
    rij = json.dumps({"bestand": "a.pdf", "besluit": BESLUIT})
    p.write_text(f"{rij}\n{rij}\n", encoding="utf-8")
    assert by_filename(p) == {"a.pdf": BESLUIT}


def test_documents_with_the_same_origin_land_in_one_dossier(session):
    for naam in ("a.pdf", "b.pdf"):
        register(session, f"documents/{naam}", filename=naam)
    session.commit()
    stats = assign(session, {"a.pdf": BESLUIT, "b.pdf": BESLUIT})
    session.commit()
    assert stats["toegewezen"] == 2
    assert list(stats["per_dossier"]) == [naam_van(BESLUIT)]
    ids = dossiers.resolve(session, naam_van(BESLUIT))
    assert len(dossiers.documents_in(session, ids)) == 2


def test_a_document_without_provenance_is_left_alone(session):
    """A classification derived from a date or a text pattern is one nobody can
    retell afterwards, and that is worse than none."""
    register(session, "documents/a", filename="a.pdf")
    naamloos = register(session, "documents/b")
    session.commit()
    stats = assign(session, {"a.pdf": BESLUIT})
    session.commit()
    assert stats["toegewezen"] == 1 and stats["zonder_herkomst"] == 1
    assert dossiers_of(session, naamloos.id) == []


def test_assigning_moves_documents_out_of_the_old_dossier(session):
    oud = dossiers.ensure(session, "corpus-2026-09")
    doc = register(session, "documents/a", filename="a.pdf")
    blijft = register(session, "documents/b", filename="b.pdf")
    session.commit()
    dossiers.add(session, oud.id, doc.id)
    dossiers.add(session, oud.id, blijft.id)
    stats = assign(session, {"a.pdf": BESLUIT}, weg_uit="corpus-2026-09")
    session.commit()
    assert dossiers_of(session, doc.id) == [
        str(dossiers.resolve(session, naam_van(BESLUIT))[0])]
    assert dossiers_of(session, blijft.id) == [str(oud.id)]   # untouched
    assert stats["nergens"] == 0


def test_assigning_out_of_an_unknown_dossier_is_refused(session):
    with pytest.raises(dossiers.DossierError, match="unknown"):
        assign(session, {}, weg_uit="bestaat-niet")
