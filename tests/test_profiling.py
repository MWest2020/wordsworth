import pytest

from wordsworth.profiling import ProfilingError, profile_pdf


def test_born_digital_is_extractable(born_digital_pdf):
    metric = profile_pdf(born_digital_pdf, 10)
    assert metric["born_digital"] is True
    assert metric["chars"] > 0
    assert metric["pages"] == 1
    assert metric["bytes"] == len(born_digital_pdf)


def test_scanned_is_unprocessable(scanned_pdf):
    metric = profile_pdf(scanned_pdf, 10)
    assert metric["born_digital"] is False


def test_parser_crash_raises_not_silent(corrupt_pdf):
    with pytest.raises(ProfilingError):
        profile_pdf(corrupt_pdf, 10)


def test_threshold_boundary(born_digital_pdf):
    chars = profile_pdf(born_digital_pdf, 10)["chars"]
    # An impossibly high per-page threshold flips the classification.
    assert profile_pdf(born_digital_pdf, chars + 1)["born_digital"] is False
