from wordsworth import detectors


def test_valid_bsn_passes_elfproef():
    assert detectors.is_valid_bsn("123456782") is True


def test_invalid_bsn_and_all_zeros_rejected():
    assert detectors.is_valid_bsn("123456789") is False
    assert detectors.is_valid_bsn("000000000") is False
    assert detectors.is_valid_bsn("12345") is False


def test_valid_iban_passes_mod97():
    assert detectors.is_valid_iban("NL91ABNA0417164300") is True


def test_invalid_iban_rejected():
    assert detectors.is_valid_iban("NL00ABNA0417164300") is False


def test_redact_bsn_only_replaces_valid():
    text = "geldig 123456782 ongeldig 123456789"
    out, count = detectors.redact_bsn(text)
    assert count == 1
    assert "[BSN]" in out
    assert "123456789" in out  # invalid one untouched
    assert "123456782" not in out


def test_redact_iban_only_replaces_valid():
    out, count = detectors.redact_iban("rek NL91ABNA0417164300 fout NL00ABNA0417164300")
    assert count == 1
    assert out.count("[IBAN]") == 1
    assert "NL00ABNA0417164300" in out


def test_redact_email():
    out, count = detectors.redact_email("mail jan.jansen@haarlem.nl door")
    assert count == 1
    assert "[EMAIL]" in out
    assert "@haarlem.nl" not in out


class TestPostcode:
    """Gemeten op 200 gepubliceerde Woo-documenten, 2026-09-13.

    De taxonomie kende ADRES/POSTCODE, normalization.py had er een normaliseerder
    voor en legible.py kon `[ADRES 2]` renderen — maar niets produceerde er ooit
    een. Nul in het hele corpus, terwijl 123 volledige adressen (straat, nummer,
    postcode) de anonimisering ongeschonden overleefden: de NER-laag haalt de
    STAD weg als LOCATION en laat de rest staan.

    Dat is de verkeerde helft. Postcode plus huisnummer identificeert in
    Nederland een huishouden; de stad is het minst identificerende deel.
    """

    def test_een_postcode_wordt_gevonden(self):
        from wordsworth.detectors import find_deterministic
        spans = find_deterministic("Woont op 1404 GZ te Bussum")
        assert ("postcode", "1404 GZ", 9, 16) in spans

    def test_met_en_zonder_spatie(self):
        from wordsworth.detectors import redact_postcode
        assert redact_postcode("1404 GZ")[0] == "[POSTCODE]"
        assert redact_postcode("1404GZ")[0] == "[POSTCODE]"

    def test_een_postcode_begint_nooit_met_nul(self):
        from wordsworth.detectors import find_deterministic
        assert not [s for s in find_deterministic("0404 GZ") if s[0] == "postcode"]

    def test_kleine_letters_tellen_niet(self):
        # `1404 gz` in lopende tekst is vrijwel nooit een postcode; hoofdletters
        # zijn hier het onderscheid tussen een adres en een toevallige match.
        from wordsworth.detectors import find_deterministic
        assert not [s for s in find_deterministic("nummer 1404 gz") if s[0] == "postcode"]

    def test_een_postbus_is_geen_huishouden(self):
        # Een postbus draagt ook een postcode, maar het is een openbaar
        # contactgegeven van een organisatie. Wegredigeren maakt een Woo-besluit
        # onleesbaar zonder iemand te beschermen.
        from wordsworth.detectors import find_deterministic, redact_postcode
        tekst = "Postbus 251, 1400 AG Bussum"
        assert not [s for s in find_deterministic(tekst) if s[0] == "postcode"]
        assert redact_postcode(tekst)[1] == 0

    def test_een_adres_naast_een_postbus_wordt_wel_geraakt(self):
        # De echte vorm uit het corpus: eerst het bezoekadres, dan de postbus.
        from wordsworth.detectors import redact_postcode
        tekst = "Burgemeester de Bordesstraat 80, 1404 GZ Bussum Postbus 251, 1400 AG Bussum"
        uit, n = redact_postcode(tekst)
        assert n == 1
        assert "[POSTCODE] Bussum Postbus 251, 1400 AG" in uit

    def test_bsn_iban_en_email_blijven_werken(self):
        from wordsworth.detectors import find_deterministic
        labels = {s[0] for s in find_deterministic(
            "111222333 NL91ABNA0417164300 a@b.nl 1404 GZ")}
        assert labels == {"bsn", "iban", "email", "postcode"}
