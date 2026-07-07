import pytest

from wordsworth.extraction import ExtractionError, extract_text


def test_extracts_text_from_born_digital(born_digital_pdf):
    text = extract_text(born_digital_pdf)
    assert "born-digital" in text


def test_corrupt_raises(corrupt_pdf):
    with pytest.raises(ExtractionError):
        extract_text(corrupt_pdf)
