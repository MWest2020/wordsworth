"""Deterministic, high-precision PII detectors. No ML — each candidate is
validated (elfproef / mod-97) before it is replaced, so shape-only matches that
fail validation are left untouched."""
from __future__ import annotations

import re

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


def _redact(text: str, pattern: re.Pattern[str], placeholder: str, validate) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        value = match.group(0)
        if validate is None or validate(value):
            count += 1
            return placeholder
        return value

    return pattern.sub(repl, text), count


def redact_bsn(text: str) -> tuple[str, int]:
    return _redact(text, _BSN_RE, "[BSN]", is_valid_bsn)


def redact_iban(text: str) -> tuple[str, int]:
    return _redact(text, _IBAN_RE, "[IBAN]", is_valid_iban)


def redact_email(text: str) -> tuple[str, int]:
    return _redact(text, _EMAIL_RE, "[EMAIL]", None)
