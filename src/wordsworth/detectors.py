"""Deterministic, high-precision PII detectors. No ML — each candidate is
validated (elfproef / mod-97) before it is replaced, so shape-only matches that
fail validation are left untouched.

`DETECTORS` and `substitute` are the shared building blocks used by both the
irreversible anonymizer and the reversible pseudonymizer."""
from __future__ import annotations

import re
from typing import Callable

_BSN_RE = re.compile(r"\b\d{9}\b")
_BSN_WEIGHTS = (9, 8, 7, 6, 5, 4, 3, 2, -1)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Dutch postcode. Four digits (never starting at 0) plus two letters, with an
# optional space. Deliberately case-sensitive on the letters: `1404 GZ` is a
# postcode, `1404 gz` in running prose almost never is.
#
# Why this is here at all — measured on 200 published Woo documents,
# 2026-09-13. The taxonomy knows ADRES/ADDRESS/POSTCODE, `normalization.py`
# has a `_postcode()` normaliser registered for it, and `legible.py` can
# render `[ADRES 2]`. Nothing ever produced one: **zero** ADDRESS and zero
# POSTCODE spans in the whole corpus. Meanwhile 123 complete addresses
# (street + number + postcode) survived anonymisation untouched, because the
# NER layer removes the CITY as a LOCATION and leaves the rest.
#
# That is the wrong half. In the Netherlands a postcode plus house number
# identifies a household; the city is the least identifying part of an
# address. The pipeline was removing the least and keeping the most.
_POSTCODE_RE = re.compile(r"\b[1-9][0-9]{3}\s?[A-Z]{2}\b")
# Postcodes that are not an address: PO boxes carry one too, and a PO box is
# an organisation's public contact detail, not a household. Left alone on
# purpose — redacting them makes a Woo decision unreadable without
# protecting anybody.
_POSTBUS_RE = re.compile(r"[Pp]ostbus\s+\d+[,.\s]{1,4}$")


def is_valid_bsn(digits: str) -> bool:
    if len(digits) != 9 or not digits.isdigit() or int(digits) == 0:
        return False
    total = sum(int(d) * w for d, w in zip(digits, _BSN_WEIGHTS))
    return total % 11 == 0


def is_valid_iban(candidate: str) -> bool:
    rearranged = candidate[4:] + candidate[:4]
    try:
        numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    except ValueError:
        return False
    return int(numeric) % 97 == 1


def _postcode_context(text: str, start: int) -> bool:
    """Is this postcode part of a PO box line?

    The validator gets only the matched value, so this is applied through a
    closure over the text in `find_deterministic` / `substitute`. A bare
    signature cannot see context, and context is the whole difference between a
    household and a mailbox.
    """
    return _POSTBUS_RE.search(text[max(0, start - 40):start]) is None


# label, pattern, validator (None = no validation). Shared by anonymizer and
# pseudonymizer so both cover exactly the same PII.
DETECTORS: list[tuple[str, re.Pattern[str], Callable[[str], bool] | None]] = [
    ("bsn", _BSN_RE, is_valid_bsn),
    ("iban", _IBAN_RE, is_valid_iban),
    ("email", _EMAIL_RE, None),
    ("postcode", _POSTCODE_RE, None),
]


def find_deterministic(text: str) -> list[tuple[str, str, int, int]]:
    """Every validated deterministic hit as ``(label, value, start, end)`` — the
    shared span view used by the PII eval and the dataset column validation."""
    out: list[tuple[str, str, int, int]] = []
    for label, pattern, validate in DETECTORS:
        for m in pattern.finditer(text):
            if validate is not None and not validate(m.group(0)):
                continue
            if label == "postcode" and not _postcode_context(text, m.start()):
                continue
            out.append((label, m.group(0), m.start(), m.end()))
    return out


def substitute(text, pattern, replacer, validate) -> tuple[str, int]:
    """Replace each validated match via ``replacer(value) -> str``; count them."""
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        value = match.group(0)
        if validate is None or validate(value):
            count += 1
            return replacer(value)
        return value

    return pattern.sub(repl, text), count


def redact_bsn(text: str) -> tuple[str, int]:
    return substitute(text, _BSN_RE, lambda v: "[BSN]", is_valid_bsn)


def redact_iban(text: str) -> tuple[str, int]:
    return substitute(text, _IBAN_RE, lambda v: "[IBAN]", is_valid_iban)


def redact_email(text: str) -> tuple[str, int]:
    return substitute(text, _EMAIL_RE, lambda v: "[EMAIL]", None)


def redact_postcode(text: str) -> tuple[str, int]:
    """Replace postcodes, except the ones on a PO box line."""
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        if not _postcode_context(text, match.start()):
            return match.group(0)
        count += 1
        return "[POSTCODE]"

    return _POSTCODE_RE.sub(repl, text), count
