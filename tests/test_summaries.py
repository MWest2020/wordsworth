# SPDX-License-Identifier: MIT
"""Samenvattingen per document (samenvattingen).

De belangrijkste test hier is de tokentest. Een citaat kan geen token verzinnen;
gegenereerde tekst wel, en tokens lossen op via een globale mappingstore — een
verzonnen `[PERSOON:aabbccdd]` is iemand, alleen niet iemand uit dit document.
"""
from __future__ import annotations

from wordsworth import summaries
from wordsworth.generator import GenerationError
from wordsworth.models import DocumentSummary, DocumentText
from wordsworth.pipeline import register


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
    doc = register(session, f"documents/{id(tekst)}")
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
        add(s, d.id, doc.id, actor="test")
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
        add(s, d.id, doc.id, actor="test")
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


def test_an_interrupted_run_keeps_what_it_already_made(session_factory):
    """Tien documenten kostten op productie meer dan een kwartier, en de run
    werd afgekapt. Met één commit aan het eind was al dat werk weg.

    Bij werk dat per stuk minuten kost hoort elk stuk dat af is, ook af te zijn
    — en houdt geen enkele transactie uren een leeslock vast, want daar liep de
    uitrol van 18-09 op stuk.
    """
    class ValtUit:
        def __init__(self):
            self.n = 0

        def generate(self, query, sources):     # pragma: no cover
            raise AssertionError

        def summarise(self, text: str) -> str:
            self.n += 1
            if self.n > 2:
                raise KeyboardInterrupt("afgekapt")
            return f"Samenvatting {self.n}."

    with session_factory() as s:
        ids = [_doc(s, f"Document nummer {i}.").id for i in range(5)]
        s.commit()
        try:
            summaries.compute(s, ValtUit(), ids, model="test")
        except KeyboardInterrupt:
            pass
        s.rollback()

    with session_factory() as tweede:
        bewaard = summaries.by_document(tweede, ids)
        assert len(bewaard) == 2, "het werk dat af was is weg"


def test_another_writer_does_not_knock_the_run_over(session_factory):
    """Gemeten op 2026-09-19: een handmatige run en een Job liepen elkaar in de
    weg en de Job viel om op `duplicate key` — ná dertien minuten werk.

    `compute()` kijkt aan het begin één keer wat er al is, en tussen dat moment
    en het schrijven zit bij een taalmodel een kwartier. Lezen-dan-schrijven is
    daar geen controle maar een gok.
    """
    with session_factory() as s:
        doc = _doc(s, "Een besluit over een dakkapel.")
        doc_id = doc.id
        s.commit()

    with session_factory() as eerste:
        # `compute` heeft net vastgesteld dat er nog niets is...
        bestaand = summaries.by_document(eerste, [doc_id])
        assert bestaand == {}

        # ...en ondertussen schrijft een ander er wel een.
        with session_factory() as ander:
            summaries.for_document(ander, Model("Van de ander."), doc_id, "ander")
            ander.commit()

        # Dit mag geen IntegrityError geven maar gewoon de nieuwste schrijven.
        rij = summaries.for_document(eerste, Model("Van mij."), doc_id, "mij")
        eerste.commit()
        assert rij.text == "Van mij."

    with session_factory() as derde:
        opnieuw = summaries.by_document(derde, [doc_id])[doc_id]
        assert opnieuw.text == "Van mij." and opnieuw.model == "mij"


def test_a_removed_token_leaves_a_visible_mark(session_factory):
    """De eerste productierun gaf "de effecten van de aanzanding op het  en geeft
    aanbevelingen": het gat leest als een taalfout in plaats van als een
    weglating, en dan twijfelt de lezer aan het model."""
    with session_factory() as s:
        doc = _doc(s, "Een rapport.")
        summaries.compute(s, Model("De melding van [PERSOON:3fa9c2d1] is ontvangen."),
                          [doc.id], model="test")
        tekst = s.get(DocumentSummary, doc.id).text
        assert tekst == "De melding van … is ontvangen."


def test_two_removals_side_by_side_read_as_one(session_factory):
    with session_factory() as s:
        doc = _doc(s, "Een rapport.")
        summaries.compute(
            s, Model("Betreft [PERSOON:3fa9c2d1] [ADRES:11223344] en de regeling."),
            [doc.id], model="test")
        assert s.get(DocumentSummary, doc.id).text == "Betreft … en de regeling."


def test_a_bare_pseudonym_id_is_removed_too(session_factory):
    """Gemeten op 2026-09-19: het model schreef "op locatie 9e9d0346, met hulp
    van organisatie a4e276dd" — het had de tokens geparafraseerd en de haken
    laten vallen. Het filter zocht de volledige vorm en liet die staarten staan.

    Die acht tekens ZIJN de sleutel: stabiel over documenten heen, dus ze
    koppelen "dit stuk en dat stuk gaan over dezelfde persoon" zonder dat er
    ooit iets onthuld wordt. En tussen haken teruggezet accepteert de reveal ze.
    """
    with session_factory() as s:
        doc = _doc(s, "Een rapport.")
        summaries.compute(
            s, Model("Stroom op locatie 9e9d0346, met hulp van organisatie a4e276dd."),
            [doc.id], model="test")
        tekst = s.get(DocumentSummary, doc.id).text
        assert "9e9d0346" not in tekst and "a4e276dd" not in tekst
        assert "Stroom op locatie" in tekst


def test_ordinary_words_are_not_mistaken_for_an_id(session_factory):
    """Acht letters uit a-f zijn ook gewoon Nederlandse woorden. Een filter dat
    "beoefend" wegpoetst is erger dan het gat dat het dicht."""
    with session_factory() as s:
        doc = _doc(s, "Een rapport.")
        summaries.compute(s, Model("De adviseur heeft beoefend en afgedaan."),
                          [doc.id], model="test")
        assert s.get(DocumentSummary, doc.id).text == (
            "De adviseur heeft beoefend en afgedaan.")

BRIEF = """[ORGANIZATION:521364bf]

Industrieweg 23a
[POSTCODE:f25614ca], [LOCATION:72c03a7e]

-- 3 --

Betreft: bezwaar tegen de geweigerde omgevingsvergunning voor een dakkapel
Kenmerk: Z/26/0032
Datum: 14 maart 2026

Geachte heer/mevrouw, hierbij dient de betrokkene bezwaar in."""


def test_the_extractive_variant_takes_the_lines_that_say_something(session_factory):
    """Bij bestuurlijke post staat juist bovenaan wat je wilt weten: afzender,
    kenmerk, datum, onderwerp. Nul modelaanroepen, dus nul seconden — tegenover
    123 seconden per document op deze hardware."""
    uit = summaries.extractive(BRIEF)
    # Vanaf het ONDERWERP, niet vanaf het briefhoofd: dat is waar een mens naar
    # zoekt. Het label zelf is geen zin.
    assert uit.startswith("bezwaar tegen de geweigerde omgevingsvergunning")
    assert "Kenmerk: Z/26/0032" in uit
    # Regels die niets benoemen -- paginastreepjes, losse leestekens -- vallen weg.
    assert "-- 3 --" not in uit
    # En het briefhoofd staat er niet meer voor.
    assert "Industrieweg" not in uit


def test_the_extractive_variant_strips_tokens_too(session_factory):
    """Hij belandt op hetzelfde scherm, dus dezelfde regel."""
    uit = summaries.extractive(BRIEF)
    assert "521364bf" not in uit and "[" not in uit


def test_it_is_a_citation_and_says_so(session_factory):
    """Het verschil dat deze hele functie rechtvaardigt: een extractieve
    samenvatting is terug te vinden in de opgeslagen tekst, een
    modelsamenvatting is een bewering."""
    with session_factory() as s:
        doc = _doc(s, BRIEF)
        uit = summaries.compute(s, None, [doc.id], model="genegeerd")
        assert uit.made == 1
        rij = s.get(DocumentSummary, doc.id)
        assert rij.model == summaries.EXTRACTIEF
        assert summaries.is_citation(rij.model)
        assert not summaries.is_citation("llama3.2:3b")
        # En het is echt een citaat: de uitvoer is niets anders dan
        # brongregels achter elkaar. Dit loopt hem letterlijk af -- blijft er
        # iets over, dan staat er tekst die nergens vandaan komt.
        # Een bronregel telt mee in zijn geheel, óf -- als het de
        # onderwerpregel is -- vanaf het onderwerp. Verder mag er niets bij
        # verzonnen zijn.
        bron = []
        for r in BRIEF.splitlines():
            kaal = summaries.clean(r)
            if not kaal:
                continue
            bron.append(kaal)
            gevonden = summaries._ONDERWERP.match(kaal)
            if gevonden and gevonden.group(2).strip():
                bron.append(gevonden.group(2).strip())
        rest = rij.text.rstrip("…")
        veranderd = True
        while rest and veranderd:
            veranderd = False
            for regel in bron:
                if rest.startswith(regel):
                    rest = rest[len(regel):].lstrip()
                    veranderd = True
                    break
        assert rest == "", f"niet uit brongregels opgebouwd, over: {rest!r}"


def test_a_document_of_only_noise_gets_no_extractive_summary(session_factory):
    with session_factory() as s:
        doc = _doc(s, "-- 1 --\n\n...\n\n[PERSOON:3fa9c2d1]\n")
        uit = summaries.compute(s, None, [doc.id], model="genegeerd")
        assert (uit.made, uit.failed) == (0, 1)
        assert s.get(DocumentSummary, doc.id) is None


MAIL = """To: raad@gooisemeren.nl
Cc:
From: JERE <EMAIL>
Sent: Mon 6/17/2024 7:27:08 PM
Subject: Advies over de aanvullende bezwaarprocedure
Attachments: 2020-02-03 advies.pdf (25 pages)

Goedemorgen, dit is het advies van de commissie over de aanvraag."""

GESCAND = """LkO1 GEDEELD PGC KfbjCNOqO+k1 ZAK V

Z2024-003438

Onderwerp: advies bestemmingsplan voor het toevoegen van een woning

Hierbij wil ik advies opvragen voor het toevoegen van een woning."""


def test_the_extract_starts_at_the_subject_line(session_factory):
    """Bij bestuurlijke post staat op de onderwerpregel letterlijk waar het stuk
    over gaat, en die staat zelden bovenaan. Gemeten op het Woo-corpus: waar zo
    n regel staat is het extract meteen raak, begint het bij regel één dan lees
    je eerst een briefhoofd."""
    uit = summaries.extractive(GESCAND)
    assert uit.startswith("advies bestemmingsplan voor het toevoegen van een woning")
    # Het label zelf is geen zin.
    assert not uit.lower().startswith("onderwerp")


def test_mail_headers_are_skipped_but_the_subject_is_not(session_factory):
    """"To: Cc From: Sent: Received:" was in het corpus de hele eerste regel van
    menig document. Het onderwerp is juist het doelwit."""
    uit = summaries.extractive(MAIL)
    assert uit.startswith("Advies over de aanvullende bezwaarprocedure")
    for kop in ("To:", "Cc:", "Sent:", "Attachments:"):
        assert kop not in uit
    assert "dit is het advies van de commissie" in uit


ZONDER_ONDERWERP = """To: raad@gooisemeren.nl
From: JERE <EMAIL>
Sent: Mon 6/17/2024 7:27:08 PM
Attachments: 2020-02-03 advies.pdf

Goedemorgen, hierbij de annotaties voor de vergadering van volgende week."""


def test_mail_headers_are_skipped_even_without_a_subject_line(session_factory):
    """Zónder onderwerpregel is er geen startpunt dat de koppen toevallig
    overslaat — dan moet het overslaan zelf het werk doen.

    Mijn eerste versie van de test hierboven had wél een onderwerpregel en
    slaagde dus ook mét het koppenfilter eruit: hij bewaakte niets.
    """
    uit = summaries.extractive(ZONDER_ONDERWERP)
    assert uit.startswith("Goedemorgen, hierbij de annotaties")
    for kop in ("To:", "From:", "Sent:", "Attachments:"):
        assert kop not in uit


def test_scanner_noise_is_skipped_not_summarised(session_factory):
    """Streepjescodes en stempels: `LkO1 GEDEELD PGC KfbjCNOqO+k1 ZAK V`. De
    regel eronder is vaak wél bruikbaar, dus overslaan en niet stoppen.

    Zónder onderwerpregel, want met een onderwerpregel begint het extract daar
    toch al en slaagt deze test ook met het rommelfilter eruit — dat had mijn
    eerste versie, en die bewaakte dus niets.
    """
    rommelig = ("LkO1 GEDEELD PGC KfbjCNOqO+k1 ZAK V\n\n"
                "Hierbij wil ik advies opvragen voor het toevoegen van een woning.")
    uit = summaries.extractive(rommelig)
    assert "KfbjCNOqO" not in uit and "LkO1" not in uit
    assert uit.startswith("Hierbij wil ik advies opvragen")


def test_ordinary_administrative_lines_are_not_mistaken_for_noise(session_factory):
    """Een filter dat gewone briefhoofden wegpoetst is erger dan de ruis die het
    weghaalt. Deze regel heeft cijfers en kenmerken en is gewoon bruikbaar."""
    regel = "Behandeld door Datum Zaaknummer 1076024 Ons kenmerk HZ_WABQO-18-2010"
    assert not summaries._is_rommel(regel)


def test_without_a_subject_line_it_still_starts_at_the_top(session_factory):
    """Niet elk document heeft een onderwerpregel. Dan blijft het gedrag zoals
    het was: de eerste regels die iets zeggen."""
    uit = summaries.extractive("Geachte heer,\n\nHierbij bevestigen wij de "
                               "ontvangst van uw aanvraag.")
    assert uit.startswith("Geachte heer,")


def test_it_is_still_a_citation_after_all_this_skipping(session_factory):
    """Overslaan mag; verzinnen niet. Alles wat overblijft moet nog steeds
    letterlijk uit het document komen."""
    uit = summaries.extractive(GESCAND).rstrip("…")
    bron = " ".join(summaries.clean(r) for r in GESCAND.splitlines())
    for stuk in uit.split(" Hierbij")[0:1]:
        assert stuk.strip() in bron


def test_a_bare_subject_label_starts_at_the_line_after_it(session_factory):
    """Gemeten op productie: in een geëxporteerde e-mail staat er letterlijk
    `Subject:` op een eigen regel en het onderwerp op de volgende. Mijn eerste
    versie viel dan terug op het label zelf, en toonde "Subject:" als
    samenvatting — het enige antwoord dat nog slechter is dan geen.
    """
    uit = summaries.extractive(
        "To: raad@gooisemeren.nl\nSubject:\n"
        "Acute opvangsituatie en stand van zaken\n\n"
        "Beste collega, bij deze stuur ik jullie de annotaties.")
    assert uit.startswith("Acute opvangsituatie en stand van zaken")
    assert "Subject:" not in uit
