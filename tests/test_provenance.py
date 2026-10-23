import pytest

from wordsworth.provenance import ProvenanceError, parse_fetched_at, validate_source_url


def test_valid_https_url_accepted():
    assert validate_source_url("https://example.org/publicatie.pdf") == \
        "https://example.org/publicatie.pdf"


def test_non_https_scheme_rejected():
    with pytest.raises(ProvenanceError, match="https"):
        validate_source_url("ftp://example.org/x.pdf")


def test_url_without_host_rejected():
    with pytest.raises(ProvenanceError, match="https"):
        validate_source_url("https:///no-host")


def test_url_over_length_limit_rejected():
    long_url = "https://example.org/" + "a" * 2048
    with pytest.raises(ProvenanceError, match="2048"):
        validate_source_url(long_url)


def test_valid_iso8601_with_timezone_parsed():
    value = parse_fetched_at("2026-10-23T12:00:00+00:00")
    assert value.year == 2026 and value.tzinfo is not None


def test_fetched_at_without_timezone_rejected():
    with pytest.raises(ProvenanceError, match="timezone"):
        parse_fetched_at("2026-10-23T12:00:00")


def test_fetched_at_not_a_date_rejected():
    with pytest.raises(ProvenanceError, match="ISO-8601"):
        parse_fetched_at("not-a-date")
