"""Een geïnjecteerd pseudonym mag nooit andermans klare waarde onthullen.

De mapping-store zoekt op pseudonym, niet per document — bewust, want dezelfde
waarde hoort overal hetzelfde token te krijgen. Zonder verdediging kan iemand
tokens uit een document dat hij mag inzien in zijn EIGEN document zetten en ze
daar onthullen met een grant die netjes op dat eigen document gescoped is
(security-review 2026-09-06, CRITICAL).
"""
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.pseudonymizer import Pseudonymizer, neutralise_foreign_tokens


def _p():
    return Pseudonymizer(InMemoryKeyProvider(), InMemoryMappingStore())


def test_token_van_een_ander_document_overleeft_de_ingest_niet():
    import re
    slachtoffer = _p()
    uitvoer = slachtoffer.anonymize("Contact: jan@example.org").text
    token = re.search(r"\[EMAIL:[0-9a-f]{8}\]", uitvoer).group(0)

    # De aanvaller zet dat token letterlijk in zijn eigen document.
    aanvaller = _p()
    uit = aanvaller.anonymize(f"Zie {token} voor details.")
    assert token not in uit.text, "geinjecteerd token overleefde de ingest"
    assert uit.text == f"Zie ({token[1:-1]}) voor details."
    assert uit.counts["FOREIGN_TOKEN_NEUTRALISED"] == 1


def test_gewone_tekst_met_haakjes_blijft_ongemoeid():
    t, n = neutralise_foreign_tokens("Zie [bijlage 3] en [PERSON:xx] en [ABC:12345678].")
    assert n == 1                      # alleen de laatste heeft de tokenvorm
    assert "[bijlage 3]" in t and "[PERSON:xx]" in t and "(ABC:12345678)" in t


def test_neutralisatie_telt_mee_in_de_counts_zodat_het_zichtbaar_is():
    p = _p()
    r = p.anonymize("[EMAIL:deadbeef] en [BSN:cafebabe]")
    assert r.counts["FOREIGN_TOKEN_NEUTRALISED"] == 2


def test_geen_valse_melding_bij_schone_tekst():
    p = _p()
    r = p.anonymize("Gewone tekst zonder tokens.")
    assert "FOREIGN_TOKEN_NEUTRALISED" not in r.counts
