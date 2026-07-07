from wordsworth.anonymizer import (
    Anonymizer,
    AnonymizationResult,
    DeterministicAnonymizer,
)


def test_deterministic_anonymizer_satisfies_protocol():
    assert isinstance(DeterministicAnonymizer(), Anonymizer)


def test_replaces_all_types_with_counts():
    text = "BSN 123456782 IBAN NL91ABNA0417164300 mail jan.jansen@haarlem.nl rest"
    result = DeterministicAnonymizer().anonymize(text)
    assert result.counts == {"email": 1, "iban": 1, "bsn": 1}
    for secret in ("123456782", "NL91ABNA0417164300", "jan.jansen@haarlem.nl"):
        assert secret not in result.text
    assert "rest" in result.text
    assert "[BSN]" in result.text and "[IBAN]" in result.text and "[EMAIL]" in result.text


def test_clean_text_is_unchanged_with_zero_counts():
    result = DeterministicAnonymizer().anonymize("gewoon een zin zonder pii")
    assert result.text == "gewoon een zin zonder pii"
    assert result.counts == {"email": 0, "iban": 0, "bsn": 0}


def test_result_carries_no_reverse_mapping():
    result = DeterministicAnonymizer().anonymize("BSN 123456782")
    # AnonymizationResult exposes only text + counts — no mapping field.
    assert set(vars(result)) == {"text", "counts"}
