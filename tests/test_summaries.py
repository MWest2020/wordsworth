# SPDX-License-Identifier: MIT
"""Samenvattingen per document (samenvattingen).

De belangrijkste test hier is de tokentest. Een citaat kan geen token verzinnen;
gegenereerde tekst wel, en tokens lossen op via een globale mappingstore — een
verzonnen `[PERSOON:aabbccdd]` is iemand, alleen niet iemand uit dit document.
"""
from __future__ import annotations

from wordsworth import summaries
from wordsworth.generator import GenerationError
from wordsworth.models import Document, DocumentSummary, DocumentText


class Model:
    def __init__(self, tekst="Het besluit gaat over een dakkapel."):
        self.tekst, self.aanroepen = tekst, []

    def generate(self, query, sources):        # pragma: no cover - niet gebruikt
        raise AssertionError("summarise, niet generate")

    def summarise(self, text: str) -> str:
        self.aanroepen.append(text)
        return self.tekst


class Kapot:
    def generate(self, query, sources):        # pragma: no cover
        raise AssertionError
    def summarise(self, text: str) -> str:
        raise GenerationError("ollama weg")


def _doc(session, tekst="De aanvraag voor een dakkapel is afgewezen."):
    doc = Document(object_key=f"documents/{id(tekst)}")
    session.add(doc)
    session.flush()
    if tekst is not None:
        session.merge(DocumentText(document_id=doc.id, anonymized_text=tekst))
    session.flush()
    return doc


def test_it_makes_and_stores_one(session_factory):
    with session_factory() as s:
        doc = _doc(s)
        uit = summaries.compute(s, Model(), [doc.id], model="llama3.2:3b")
        assert (uit.seen, uit.made, uit.skipped, uit.failed) == (1, 1, 0, 0)
        rij = s.get(DocumentSummary, doc.id)
        assert rij.text == "Het besluit gaat over een dakkapel."
        assert rij.model == "llama3.2:3b" and rij.created_at


def test_a_token_never_survives_into_a_summary(session_factory):
    """De spec-eis. Het model krijgt de instructie geen tokens over te nemen --
    dat is een verzoek. Dit is de garantie.

    Let op wat hier gebeurt: het model verzint `[PERSOON:aabbccdd]`, dat NIET in
    het document staat. Bleef dat staan, dan koppelt deze samenvatting een
    vreemde aan dit stuk, en een onthulling erop levert diens klare naam binnen
    een grant die op dít document gescoped is.
    """
    with session_factory() as s:
        doc = _doc(s, "De aanvraag van [PERSOON:3fa9c2d1] is afgewezen.")
        model = Model("Het besluit betreft [PERSOON:aabbccdd] en [ADRES:11223344].")
        summaries.compute(s, model, [doc.id], model="test")
        tekst = s.get(DocumentSummary, doc.id).text
        assert "aabbccdd" not in tekst and "11223344" not in tekst
        assert "[" not in tekst
        assert "Het besluit betreft" in tekst


def test_a_failed_generation_leaves_nothing_behind(session_factory):
    """Een placeholder die eruitziet als inhoud is erger dan een leeg veld: hij
    wordt gelezen als de samenvatting van een document dat niemand heeft
    samengevat."""
    with session_factory() as s:
        doc = _doc(s)
        uit = summaries.compute(s, Kapot(), [doc.id], model="test")
        assert (uit.made, uit.failed) == (0, 1)
        assert s.get(DocumentSummary, doc.id) is None


def test_an_empty_answer_is_not_a_summary(session_factory):
    with session_factory() as s:
        doc = _doc(s)
        uit = summaries.compute(s, Model("   "), [doc.id], model="test")
        assert (uit.made, uit.failed) == (0, 1)
        assert s.get(DocumentSummary, doc.id) is None


def test_a_summary_that_is_only_tokens_is_not_a_summary(session_factory):
    """Na het filteren blijft er niets over. Dan is er niets samengevat."""
    with session_factory() as s:
        doc = _doc(s)
        uit = summaries.compute(s, Model("[PERSOON:3fa9c2d1] [ADRES:11223344]"),
                                [doc.id], model="test")
        assert (uit.made, uit.failed) == (0, 1)
        assert s.get(DocumentSummary, doc.id) is None


def test_running_again_does_not_redo_the_work(session_factory):
    """Bij een taalmodel is dit geen optimalisatie maar het verschil tussen een
    knop die je durft in te drukken en een die je vermijdt."""
    with session_factory() as s:
        doc = _doc(s)
        model = Model()
        summaries.compute(s, model, [doc.id], model="test")
        opnieuw = summaries.compute(s, model, [doc.id], model="test")
        assert (opnieuw.made, opnieuw.skipped) == (0, 1)
        assert len(model.aanroepen) == 1, "het model is twee keer aangeroepen"


def test_a_document_without_text_is_counted_not_hidden(session_factory):
    with session_factory() as s:
        doc = _doc(s, None)
        uit = summaries.compute(s, Model(), [doc.id], model="test")
        assert (uit.made, uit.failed, uit.without_text) == (0, 0, 1)


def test_the_model_sees_the_pseudonymised_text(session_factory):
    """En niets anders. Er is geen andere tekst, en als die er ooit is moet dit
    omvallen in plaats van hem stilletjes te gebruiken."""
    with session_factory() as s:
        doc = _doc(s, "De aanvraag van [PERSOON:3fa9c2d1] is afgewezen.")
        model = Model()
        summaries.compute(s, model, [doc.id], model="test")
        assert model.aanroepen == ["De aanvraag van [PERSOON:3fa9c2d1] is afgewezen."]


def test_the_screen_says_it_was_generated_and_by_what(session_factory):
    """De spec-eis: een samenvatting staat naast het citaat en is herkenbaar een
    bewering. Alles wat dit systeem verder toont is terug te voeren op iets dat
    is opgeslagen; deze zin niet."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.dossiers import add, ensure
    from wordsworth.search_index import InMemoryIndex

    index = InMemoryIndex()
    with session_factory() as s:
        d = ensure(s, "zaak")
        s.flush()
        doc = _doc(s, "De aanvraag voor een dakkapel is afgewezen.")
        add(s, d.id, doc.id)
        index.index(str(doc.id), "De aanvraag voor een dakkapel is afgewezen.",
                    doc.object_key, dossiers=[str(d.id)])
        summaries.compute(s, Model("Het gaat over een geweigerde dakkapel."),
                          [doc.id], model="llama3.2:3b")
        s.commit()

    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"s3cret": "mark"}, search_index=index),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    pagina = c.get("/console/search",
                   params={"q": "dakkapel", "dossier": "zaak"}).text
    assert "Het gaat over een geweigerde dakkapel." in pagina
    assert "llama3.2:3b" in pagina
    assert "geen citaat" in pagina, "een bewering hoort als bewering te staan"
    # En het citaat staat er nog, niet eronder weg.
    assert "De aanvraag voor een dakkapel is afgewezen" in pagina


def test_a_document_without_one_says_so_instead_of_being_blank(session_factory):
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.dossiers import add, ensure
    from wordsworth.search_index import InMemoryIndex

    index = InMemoryIndex()
    with session_factory() as s:
        d = ensure(s, "zaak2")
        s.flush()
        doc = _doc(s, "Een notulen over parkeren.")
        add(s, d.id, doc.id)
        index.index(str(doc.id), "Een notulen over parkeren.", doc.object_key,
                    dossiers=[str(d.id)])
        s.commit()

    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"s3cret": "mark"}, search_index=index),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    pagina = c.get("/console/search",
                   params={"q": "parkeren", "dossier": "zaak2"}).text
    assert "nog geen samenvatting" in pagina


def test_the_endpoint_is_behind_the_corpus_gate(session_factory):
    """Een samenvatting zegt waar een document over gaat. Dat is dezelfde soort
    kennis als de opgeslagen tekst, en hoort achter dezelfde poort."""
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from wordsworth.api import create_app

    app = create_app(session_factory=session_factory,
                     api_keys={"s3cret": "mark"},
                     corpus_read_labels=["iemand-anders"],
                     generator=Model())
    c = TestClient(app, base_url="https://testserver")
    r = c.post(f"/dossiers/{uuid4()}/summaries",
               headers={"x-api-key": "s3cret", "Accept": "application/json"})
    assert r.status_code == 403
