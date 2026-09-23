"""add-detection-feedback: typed allow/deny lists, hash in audit, feedback event."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.detection_lists import DetectionLists
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.models import AuditRecord
from wordsworth.openanonymiser_driver import Entity, OpenAnonymiserAnonymizer
from wordsworth.pseudonymizer import ReversibleAnonymizer

PII_BSN = "123456782"


def _lists(tmp_path, allow=None, deny=None):
    """Schrijft de twee bestanden en laadt ze.

    Een allow-regel krijgt hier automatisch een reden mee: die is sinds
    2026-09-20 verplicht (een allow-regel haalt bescherming weg, en een kale
    lijst woorden is niet na te kijken). Deze tests gaan over het mechanisme,
    niet over die eis -- die heeft een eigen test in
    `test_allow_list_veiligheid.py`.
    """
    met_reden = {t: [{"patroon": p, "reden": "test"} for p in pats]
                 for t, pats in (allow or {}).items()}
    (tmp_path / "allow.json").write_text(json.dumps(met_reden))
    (tmp_path / "deny.json").write_text(json.dumps(deny or {}))
    return DetectionLists.load(tmp_path)


def test_typed_false_positive_is_suppressed_never_across_types(tmp_path):
    lists = _lists(tmp_path, allow={"PERSON": ["^Jansen BV$"]})
    text = "Jansen BV leverde aan Jan Jansen."
    ents = [Entity("PERSON", "Jansen BV", 0, 9, "openanonymiser", 0.8),
            Entity("PERSON", "Jan Jansen", 22, 32, "openanonymiser", 0.9)]
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                             detect=lambda t: ents, lists=lists).anonymize(text)
    assert r.text.startswith("Jansen BV")          # kept in clear (not PII)
    assert "Jan Jansen" not in r.text              # real person still redacted
    assert r.detections["suppressed_by_list"]["PERSON"]["count"] == 1
    assert r.lists_hash == lists.hash and len(lists.hash) == 64
    # same pattern, other type → kept
    org = [Entity("ORGANIZATION", "Jansen BV", 0, 9, "openanonymiser", 0.8)]
    r2 = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                              detect=lambda t: org, lists=lists).anonymize(text)
    assert "Jansen BV" not in r2.text


def test_deny_adds_list_layer_detections_in_both_drivers(tmp_path):
    lists = _lists(tmp_path, deny={"KENTEKEN": [r"\b[A-Z]{2}-\d{3}-[A-Z]\b"]})
    text = f"Voertuig AB-123-C van BSN {PII_BSN}."
    rev = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                               detect=lambda t: [], lists=lists).anonymize(text)
    assert "AB-123-C" not in rev.text and "[KENTEKEN:" in rev.text
    assert rev.detections["list"]["KENTEKEN"]["count"] == 1
    irr = OpenAnonymiserAnonymizer(engine=lambda t: (t, {}), lists=lists).anonymize(text)
    assert "AB-123-C" not in irr.text and "[KENTEKEN]" in irr.text
    assert irr.detections["list"]["KENTEKEN"]["count"] == 1
    assert irr.detections["deterministic"]["BSN"]["count"] == 1
    assert irr.lists_hash == lists.hash


_URL = r"(?:https?://|www\.)[^\s<>\"'()\[\]]*[^\s<>\"'()\[\].,;:!?]"


def test_allow_wins_over_deny_for_the_same_type(tmp_path):
    """urls-are-detected: a deny rule catches every web address; an allow rule
    of the SAME type exempts a public host. Before this change allow only saw
    what the detectors found, and deny appended its matches afterwards -- so no
    exception could ever be written next to the rule it is an exception to.

    Through ReversibleAnonymizer, the path production runs, not through
    `apply` alone: a rule that only holds in a helper is how the Postbus
    exception once ran nowhere."""
    lists = _lists(
        tmp_path,
        allow={"URL": [r"(?:https?://)?(?:www\.)?wetten\.overheid\.nl(?:/\S*)?"]},
        deny={"URL": [_URL]})
    text = "Zie https://wetten.overheid.nl/BWBR0045754 en www.eazwind.nl."
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                             detect=lambda t: [], lists=lists).anonymize(text)
    assert "https://wetten.overheid.nl/BWBR0045754" in r.text    # public: kept
    assert "www.eazwind.nl" not in r.text and "[URL:" in r.text   # party: replaced
    assert r.text.endswith("].")                                 # full stop outside
    assert r.detections["suppressed_by_list"]["URL"]["count"] == 1


def test_allow_over_deny_still_never_crosses_types(tmp_path):
    lists = _lists(tmp_path,
                   allow={"LOCATION": [r"www\.eazwind\.nl"]},
                   deny={"URL": [_URL]})
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                             detect=lambda t: [], lists=lists).anonymize(
                                 "Zie www.eazwind.nl.")
    assert "www.eazwind.nl" not in r.text


def test_no_lists_is_a_noop_with_no_hash():
    lists = DetectionLists.load("")
    assert lists.hash is None
    ents = [Entity("PERSON", "Jan", 0, 3, "openanonymiser", 0.9)]
    kept, suppressed = lists.apply("Jan", ents)
    assert kept == ents and suppressed == {}


def test_malformed_list_is_hard_error(tmp_path):
    (tmp_path / "allow.json").write_text("[1,2]")
    with pytest.raises(ValueError):
        DetectionLists.load(tmp_path)
    (tmp_path / "allow.json").write_text('{"PERSON": ["("]}')
    with pytest.raises(Exception):
        DetectionLists.load(tmp_path)


def test_hash_changes_with_content(tmp_path):
    a = _lists(tmp_path, allow={"PERSON": ["^A$"]}).hash
    b = _lists(tmp_path, allow={"PERSON": ["^B$"]}).hash
    assert a != b


def test_feedback_is_audited_without_values_and_lists_untouched(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
        tmp_path):
    from wordsworth.pipeline import ingest, process
    lists = _lists(tmp_path, allow={"PERSON": ["^X$"]})
    before = lists.hash
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store, search_index=mem_index, embedder=fake_embedder)
        s.commit()
    c = TestClient(create_app(session_factory=session_factory))
    r = c.post(f"/documents/{doc.id}/feedback",
               json={"kind": "fp", "type": "person", "token": "[PERSON:3fa9c2d1]"})
    assert r.status_code == 201, r.text
    assert r.json()["recorded"] == {"kind": "fp", "type": "PERSON", "token": "[PERSON:3fa9c2d1]"}
    # a clear value cannot be smuggled in as a token; no free-text field exists
    assert c.post(f"/documents/{doc.id}/feedback",
                  json={"kind": "fp", "type": "PERSON", "token": "Jan Jansen"}).status_code == 422
    assert c.post(f"/documents/{doc.id}/feedback",
                  json={"kind": "fp", "type": "PERSON", "note": "Jan"}).status_code == 201
    assert c.post(f"/documents/{doc.id}/feedback",
                  json={"kind": "maybe", "type": "PERSON"}).status_code == 422
    with session_factory() as s:
        recs = s.execute(select(AuditRecord).where(
            AuditRecord.step == "detection_feedback")).scalars().all()
        assert len(recs) == 2 and all("Jan" not in json.dumps(r.payload) for r in recs)
        assert recs[0].from_state == recs[0].to_state == "indexed"
        anon = s.execute(select(AuditRecord).where(AuditRecord.step == "anonymize")
                         ).scalar_one()
        assert anon.payload["lists_hash"] is None       # pipeline ran without lists
    assert DetectionLists.load(tmp_path).hash == before  # lists untouched
    meta = c.get(f"/documents/{doc.id}").json()
    assert meta["lists_hash"] is None and "lists_hash" not in meta["counts"]


def test_deny_overlapping_detector_span_keeps_counts_and_aggregates_consistent(tmp_path):
    lists = _lists(tmp_path, deny={"KENTEKEN": [r"\bAB-123-C\b"]})
    ents = [Entity("PERSON", "AB-123-C", 9, 17, "openanonymiser", 0.5)]  # detector's label wins
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                             detect=lambda t: ents, lists=lists).anonymize("Voertuig AB-123-C.")
    assert "AB-123-C" not in r.text
    assert r.counts.get("kenteken", 0) == 0 and r.counts["person"] == 1
    assert "KENTEKEN" not in r.detections.get("list", {})     # loser not aggregated


# --- het straatadres (restwaarden, taak 2) -------------------------------

class TestStraatadres:
    """Een straatnaam + huisnummer is het woonadres van een natuurlijk persoon.

    De detector levert de straatnaam soms wél en het nummer nooit, waardoor
    `Kerkstraat 12` als `Kerkstraat` verdwijnt en het huisnummer blijft staan.
    Een deny-regel voegt het hele adres toe — de veilige kant op.
    """

    def _lijsten(self):
        from pathlib import Path

        from wordsworth.detection_lists import DetectionLists
        return DetectionLists.load(Path(__file__).resolve().parent.parent / "lists")

    @pytest.mark.parametrize("tekst,verwacht", [
        ("Woonachtig Kerkstraat 12, 1234 AB Haarlem.", "Kerkstraat 12"),
        ("Molenweg 118a", "Molenweg 118a"),
        ("Stationsplein 1", "Stationsplein 1"),
        ("Dorpsstraat 7", "Dorpsstraat 7"),
        # Kleine letter: zo levert de OCR het geregeld aan.
        ("adres: dorpsstraat 7", "dorpsstraat 7"),
    ])
    def test_een_adres_wordt_toegevoegd(self, tekst, verwacht):
        kept, _ = self._lijsten().apply(tekst, [])
        assert [(e.entity_type, e.text) for e in kept] == [("LOCATION", verwacht)]

    @pytest.mark.parametrize("tekst", [
        "Zie Artikel 5 en bijlage 3.",            # het genoemde valse-positief-geval
        "Postbus 1234, 1234 AB Haarlem",          # organisatie-adres, geen woonadres
        "Verandering 3 van de regeling",          # eindigt op 'ring', geen straat
        "de Groenestraat",                        # straat zonder nummer is geen adres
        "Het besluit van 12 maart",
    ])
    def test_wat_geen_adres_is_blijft_eraf(self, tekst):
        kept, _ = self._lijsten().apply(tekst, [])
        assert kept == [], f"{tekst!r} werd ten onrechte als adres gezien"

    def test_a_post_office_box_is_not_a_home_address(self):
        """"Unless specified" has a counter-case, and it is in the corpus.

        A `Postbus` line is an organisation's contact address, not where a
        person lives. Without this the rule would reward redacting every
        address-shaped thing, and the evalcorpus seeds it deliberately as
        non-gold.
        """
        kept, _ = self._lijsten().apply("Postbus 1234, 1234 AB Haarlem", [])
        assert kept == [], "een postbus is geen woonadres"

    def test_street_and_number_are_one_span(self):
        """What identifies a person is the pair. A street on its own is a
        place; a house number on its own is nothing. So the rule yields one
        entity, not two."""
        kept, _ = self._lijsten().apply("woonachtig Kerkstraat 12, 1234 AB", [])
        assert len(kept) == 1
        assert kept[0].text == "Kerkstraat 12"


class TestWebadres:
    """urls-are-detected: een webadres van een partij is een persoonsgegeven,
    een publieke host niet. Tegen de ECHTE lijsten in `lists/`, door de
    ReversibleAnonymizer -- de route die productie loopt."""

    def _anon(self, tekst):
        from pathlib import Path
        lijsten = DetectionLists.load(Path(__file__).resolve().parent.parent / "lists")
        return ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                                    detect=lambda t: [], lists=lijsten).anonymize(tekst)

    @pytest.mark.parametrize("tekst,weg", [
        ("www.eazwind.nl", "www.eazwind.nl"),                       # #124, los
        ("Meer informatie op www.eazwind.nl.", "www.eazwind.nl"),    # in een zin
        ("Zie https://www.jansen-bv.nl/contact.", "https://www.jansen-bv.nl/contact"),
        ("WWW.EAZWIND.NL", "WWW.EAZWIND.NL"),                       # OCR in kapitalen
    ])
    def test_een_partij_wordt_vervangen(self, tekst, weg):
        r = self._anon(tekst)
        assert weg not in r.text and "[URL:" in r.text

    def test_de_punt_blijft_buiten_het_token(self):
        assert self._anon("Zie www.eazwind.nl.").text.endswith("].")

    @pytest.mark.parametrize("tekst", [
        "https://wetten.overheid.nl/BWBR0045754",
        "www.rijksoverheid.nl",
        "https://www.gooisemeren.nl/bestuur",
        "www.goocisemeren.nl",                  # OCR van de gemeente zelf
        "www.ofgv.nl",
        "https://open.gelderland.nl/besluiten",
    ])
    def test_een_publieke_host_blijft_staan(self, tekst):
        r = self._anon(f"Zie {tekst} voor het besluit.")
        assert tekst in r.text and "[URL:" not in r.text

    @pytest.mark.parametrize("tekst", [
        "www.eviloverheid.nl",                  # geen subdomein, andere host
        "https://gooisemeren.nl.evil.example",  # publieke naam als voorvoegsel
    ])
    def test_een_publieke_naam_als_deel_van_een_andere_host_telt_niet(self, tekst):
        assert "[URL:" in self._anon(f"Zie {tekst} nu.").text

    def test_een_emailadres_is_niet_ook_een_webadres(self):
        r = self._anon("Mail info@eazwind.nl.")
        assert "[EMAIL:" in r.text and "[URL:" not in r.text
