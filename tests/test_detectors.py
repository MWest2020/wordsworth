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
