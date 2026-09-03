"""PII category registry (add-pii-categories-and-ppl): every PII type maps to
one AVG category — ``c1`` (Art. 6, ordinary personal data), ``c2`` (Art. 9,
special categories) or ``c3`` (Art. 10, criminal data) — and to the minimum
Privacy Protection Level (PPL 0–3) at which it may be revealed.

Static data, not code paths: PPL is *sugar* over the grant model. A grant issued
"at PPL n" is stored as the plain ``allowed_types`` this registry expands to, so
enforcement (``grants.authorize``) is untouched. Unknown detector types are
classified ``c1`` (fail-safe: never revealed at PPL 0) and logged once."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

REGISTRY_VERSION = "r1"

# category -> (legal basis, minimum PPL to reveal)
CATEGORIES: dict[str, tuple[str, int]] = {
    "c1": ("Art. 6", 1),
    "c2": ("Art. 9", 2),
    "c3": ("Art. 10", 3),
}
UNKNOWN_CATEGORY = "c1"

# Upper-case type -> category. Dutch and English/Presidio spellings both listed
# because the detector's label vocabulary is not ours to fix.
_TYPES: dict[str, str] = {
    # Art. 6 — ordinary personal data
    **{t: "c1" for t in (
        "PERSON", "PERSOON", "LOCATION", "LOCATIE", "ADRES", "ADDRESS",
        "POSTCODE", "BSN", "IBAN", "EMAIL", "EMAIL_ADDRESS", "PHONE_NUMBER",
        "TELEFOON", "DATE", "DATE_TIME", "GEBOORTEDATUM", "KENTEKEN",
        "LICENSE_PLATE", "ORGANIZATION", "ORGANISATIE", "BEDRAG", "KVK",
        "URL", "IP_ADDRESS", "OVERIG",
    )},
    # Art. 9 — special categories
    **{t: "c2" for t in (
        "GEZONDHEID", "HEALTH", "MEDICAL", "RELIGIE", "RELIGION", "ETNICITEIT",
        "ETHNICITY", "BIOMETRIE", "BIOMETRIC", "GENETISCH", "GENETIC",
        "SEKSUELE_GEAARDHEID", "SEXUAL_ORIENTATION", "POLITIEKE_OPVATTING",
        "POLITICAL_OPINION", "VAKBOND", "TRADE_UNION",
    )},
    # Art. 10 — criminal convictions and offences
    **{t: "c3" for t in ("STRAFRECHTELIJK", "CRIMINAL", "CRIMINAL_RECORD")},
}

_warned: set[str] = set()


def category_of(entity_type: str) -> str:
    """``c1``/``c2``/``c3`` for a PII type; unknown → ``c1``, warned once."""
    t = entity_type.upper()
    cat = _TYPES.get(t)
    if cat is None:
        if t not in _warned:
            _warned.add(t)
            log.warning("pii_categories: unknown type %r classified as %s", t,
                        UNKNOWN_CATEGORY)
        return UNKNOWN_CATEGORY
    return cat


def legal_basis_of(entity_type: str) -> str:
    return CATEGORIES[category_of(entity_type)][0]


def ppl_min_of(entity_type: str) -> int:
    return CATEGORIES[category_of(entity_type)][1]


def types_for_ppl(ppl: int) -> set[str]:
    """Every registered type whose category may be revealed at ``ppl``. PPL 0 is
    the empty set. Only registered types are expanded — an unknown detector
    type is never granted implicitly by a level."""
    if not 0 <= ppl <= 3:
        raise ValueError("ppl must be 0..3")
    return {t for t, c in _TYPES.items() if CATEGORIES[c][1] <= ppl}


def ppl_of_types(types) -> int | None:
    """The PPL whose expansion equals ``types`` exactly, else None."""
    wanted = {t.upper() for t in types}
    for ppl in range(0, 4):
        if types_for_ppl(ppl) == wanted:
            return ppl
    return None


def group_by_basis(types) -> dict[str, list[str]]:
    """``{"Art. 6": [...], "Art. 9": [...], "Art. 10": [...]}`` — every type
    under exactly one basis; empty bases omitted."""
    out: dict[str, list[str]] = {}
    for t in sorted({x.upper() for x in types}):
        out.setdefault(legal_basis_of(t), []).append(t)
    return out


def counts_by_category(counts: dict[str, int]) -> dict[str, int]:
    """Aggregate per-type PII counts into ``{"c1": n, "c2": n, "c3": n}``."""
    out = {c: 0 for c in CATEGORIES}
    for label, n in counts.items():
        out[category_of(label)] += int(n)
    return out
