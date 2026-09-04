"""Legible placeholder VIEW over stored token text (add-legible-placeholders).

``[PERSON:3fa9c2d1]`` is right for the index (stable across documents) and
wrong for a reader. This renders each distinct token as a numbered, Dutch-
labelled placeholder — ``[PERSOON 1]``, ``[ADRES 2]`` — numbered per type in
order of first occurrence, plus a legend back to the tokens (reveal works on
tokens, never on ordinals). Pure: nothing stored or indexed changes."""
from __future__ import annotations

from .pseudonymizer import _PSEUDONYM_RE, _label_of

# Upper-case token label -> Dutch reader label. Unknown labels pass through.
LABELS: dict[str, str] = {
    "PERSON": "PERSOON", "LOCATION": "LOCATIE", "ADDRESS": "ADRES",
    "ORGANIZATION": "ORGANISATIE", "PHONE_NUMBER": "TELEFOON",
    "DATE": "DATUM", "DATE_TIME": "DATUM", "EMAIL_ADDRESS": "EMAIL",
    "LICENSE_PLATE": "KENTEKEN", "HEALTH": "GEZONDHEID", "RELIGION": "RELIGIE",
    "ETHNICITY": "ETNICITEIT", "CRIMINAL": "STRAFRECHTELIJK",
}


def to_legible(text: str) -> tuple[str, dict[str, str]]:
    """(legible text, legend) where legend maps ``[PERSOON 1]`` -> the token."""
    ordinal: dict[str, str] = {}      # token -> placeholder
    counters: dict[str, int] = {}     # label -> last ordinal

    def repl(match) -> str:
        token = match.group(0)
        if token not in ordinal:
            label = LABELS.get(_label_of(token), _label_of(token))
            counters[label] = counters.get(label, 0) + 1
            ordinal[token] = f"[{label} {counters[label]}]"
        return ordinal[token]

    rendered = _PSEUDONYM_RE.sub(repl, text)
    return rendered, {ph: tok for tok, ph in ordinal.items()}
