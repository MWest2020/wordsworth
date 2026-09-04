"""Column-selected pseudonymisation of tabular data (add-dataset-pseudonymisation).

The dataset path of the target architecture: the operator SELECTS columns (no
detection), the engine emits consistent keyed pseudonyms per domain, the
encrypted originals go to the same separated mapping store ("lookup table"),
and re-identification is the existing grant-gated reveal on tokens. The
derivation is `Pseudonymizer.pseudonym` — the very one free text uses — so a
BSN in a document and the same BSN in a dataset cell of the same domain get the
SAME token. Streaming over stdlib ``csv``; no pandas."""
from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

from .detectors import find_deterministic
from .keys import DEFAULT_DOMAIN
from .normalization import normalize

# "NEN 7524-style" header letters (ADR-0005 D9: conformance to NEN 7524:2019 is
# UNVERIFIED — the norm text has not been checked; this mirrors the deck).
_NEN_LETTER = {"BSN": "B", "PERSON": "N", "NAAM": "N", "ADRES": "A", "ADDRESS": "A",
               "LOCATION": "A", "DATE": "D", "GEBOORTEDATUM": "D", "POSTCODE": "C",
               "RECORD": "R"}
RECORD_TYPE = "RECORD"
_SAMPLE_ROWS = 200


class Profile(BaseModel):
    """What to pseudonymise and how. Versioned in git (``profiles/<name>.json``)
    or supplied inline; hashed into the audit record."""

    domain: str = DEFAULT_DOMAIN
    columns: dict[str, str]                     # column -> PII type
    mode: Literal["per_attribute", "per_record"] = "per_attribute"
    record_key: list[str] = []                  # per_record: identity columns, in order
    format: Literal["token", "nen7524"] = "token"
    ttp_id: str = "0001"
    validate_pii: bool = False

    @model_validator(mode="after")
    def _check(self):
        if "/" in self.domain or not self.domain:
            raise ValueError("domain must be non-empty and contain no '/'")
        if not self.columns:
            raise ValueError("select at least one column")
        if self.mode == "per_record" and not self.record_key:
            raise ValueError("per_record needs record_key")
        if self.format == "nen7524":
            types = set(self.columns.values()) if self.mode == "per_attribute" else {RECORD_TYPE}
            unknown = sorted(t for t in types if t.upper() not in _NEN_LETTER)
            if unknown:   # no silent 'X' letter for a typo'd type
                raise ValueError(f"nen7524 format has no type letter for {unknown}")
        return self

    def sha256(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


def load_profile(name: str, directory: str | Path) -> Profile:
    """A named profile from the versioned directory; unknown name = hard error."""
    if "/" in name or name.startswith("."):
        raise ValueError("profile name must be a plain file stem")
    path = Path(directory) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"profile {name!r} not found in {directory}")
    return Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def render(token: str, fmt: str, ttp_id: str) -> str:
    """``token`` → output form. ``nen7524`` = ``01-<ttp>-P<letter>|<base64(hash)>``."""
    if fmt == "token":
        return token
    label, digest = token[1:-1].split(":")
    letter = _NEN_LETTER.get(label, "X")
    payload = base64.b64encode(bytes.fromhex(digest)).decode()
    return f"01-{ttp_id}-P{letter}|{payload}"


class DatasetRun:
    """Streaming transform of dict rows; collects aggregates (never values)."""

    def __init__(self, profile: Profile, pseudonymizer) -> None:
        self.profile = profile
        self._p = pseudonymizer               # has .pseudonym(label, value)
        self.rows = 0
        self.unique: set[str] = set()
        self.rows_without_record_key = 0   # per_record rows whose identity is empty

    def _record_identity(self, row: dict) -> str:
        parts = []
        for col in self.profile.record_key:
            if col not in row:
                raise KeyError(f"record_key column {col!r} missing")
            typ = self.profile.columns.get(col, RECORD_TYPE)
            parts.append(normalize(typ, row[col] or ""))
        return "|".join(parts)                # fixed order, empty cell = ""

    def transform(self, rows: Iterable[dict]) -> Iterator[dict]:
        fmt, ttp = self.profile.format, self.profile.ttp_id
        for row in rows:
            missing = [c for c in self.profile.columns if c not in row]
            if missing:
                raise KeyError(f"selected column(s) missing: {missing}")
            out = dict(row)
            if self.profile.mode == "per_record":
                identity = self._record_identity(row)
                if identity.strip("|") == "":
                    # All key cells empty: such rows collapse onto ONE shared
                    # pseudonym — counted so the operator sees the footgun.
                    self.rows_without_record_key += 1
                token = self._p.pseudonym(RECORD_TYPE, identity)
                self.unique.add(token)
                for col in self.profile.columns:
                    out[col] = render(token, fmt, ttp) if (row[col] or "") != "" else ""
            else:
                for col, typ in self.profile.columns.items():
                    value = row[col] or ""
                    if value == "":
                        continue                # nothing to pseudonymise
                    token = self._p.pseudonym(typ, value)
                    self.unique.add(token)
                    out[col] = render(token, fmt, ttp)
            self.rows += 1
            yield out

    def stats(self) -> dict:
        return {"rows": self.rows, "columns": sorted(self.profile.columns),
                "mode": self.profile.mode, "format": self.profile.format,
                "domain": self.profile.domain, "unique_pseudonyms": len(self.unique),
                "rows_without_record_key": self.rows_without_record_key,
                "profile_sha256": self.profile.sha256()}


def validate_unselected(rows: list[dict], profile: Profile) -> list[dict]:
    """Advisory: run the DETERMINISTIC detectors (BSN/IBAN/email — offline, no
    service call) over a sample of each UNSELECTED column; report columns that
    look like they hold PII. Names/addresses are not covered. Never transforms."""
    warnings: list[dict] = []
    if not rows:
        return warnings
    for col in rows[0]:
        if col in profile.columns:
            continue
        sample = "\n".join((r.get(col) or "") for r in rows[:_SAMPLE_ROWS])
        types = sorted({label.upper() for label, _, _, _ in find_deterministic(sample)})
        if types:
            warnings.append({"column": col, "types": types,
                             "hint": "kolom bevat mogelijk PII maar is niet geselecteerd"})
    return warnings
