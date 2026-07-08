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


# label, pattern, validator (None = no validation). Shared by anonymizer and
# pseudonymizer so both cover exactly the same PII.
DETECTORS: list[tuple[str, re.Pattern[str], Callable[[str], bool] | None]] = [
    ("bsn", _BSN_RE, is_valid_bsn),
    ("iban", _IBAN_RE, is_valid_iban),
    ("email", _EMAIL_RE, None),
]


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
