"""Value normalisation BEFORE pseudonym derivation (add-value-normalisation).

A pseudonym must be consistent for the same person: ``Jansen``/``jansen`` and
``1234.56.789``/``123456789`` are the same identifier and must yield the same
token, or records silently stop being linkable. Rules are typed and
table-driven; the default is trim + Unicode NFC. The *stored* (encrypted) value
is always the original spelling — normalisation only feeds the HMAC.

The profile is versioned: a rule change bumps ``PROFILE_VERSION`` and existing
corpora are re-derived through the reprocess path, never implicitly."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Callable

PROFILE_VERSION = "n1"

_SEP_RE = re.compile(r"[.\s-]")
_WS_RE = re.compile(r"\s+")
_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y%m%d")


def _default(value: str) -> str:
    """Trim + NFC: the baseline every rule builds on."""
    return unicodedata.normalize("NFC", value).strip()


def _casefold(value: str) -> str:
    return _default(value).casefold()


def _bsn(value: str) -> str:
    """Strip separators and left-pad to 9 digits; non-digit input falls back to
    the default so a garbled value still normalises deterministically."""
    digits = _SEP_RE.sub("", _default(value))
    return digits.zfill(9) if digits.isdigit() else _default(value)


def _postcode(value: str) -> str:
    return _WS_RE.sub("", _default(value)).upper()


def _date(value: str) -> str:
    """ISO 8601 when the value parses as a date in a common NL format; otherwise
    the default (never raise — an unparseable date is still a stable string)."""
    raw = _default(value)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


# Upper-case PII type -> rule. Types not listed get ``_default``.
RULES: dict[str, Callable[[str], str]] = {
    "BSN": _bsn,
    "POSTCODE": _postcode,
    "PERSON": _casefold,
    "PERSOON": _casefold,
    "LOCATION": _casefold,
    "LOCATIE": _casefold,
    "ADRES": _casefold,
    "ADDRESS": _casefold,
    "ORGANIZATION": _casefold,
    "ORGANISATIE": _casefold,
    "EMAIL": _casefold,
    "EMAIL_ADDRESS": _casefold,
    "DATE": _date,
    "DATE_TIME": _date,
    "GEBOORTEDATUM": _date,
}


def normalize(label: str, value: str) -> str:
    """The canonical form of ``value`` for PII type ``label`` (case-insensitive)."""
    return RULES.get(label.upper(), _default)(value)


__all__ = ["PROFILE_VERSION", "RULES", "normalize"]
