# SPDX-License-Identifier: MIT
"""Build a document and its ground truth in one pass (ground-truth-corpus).

The offsets are recorded while the text is written, by the step that writes it.
Annotating text afterwards is a second source of truth, and two sources of truth
about the same 500 documents will disagree — quietly, and in the direction that
flatters the score.

So there is one primitive: ``pii(value, type)`` appends the value AND records
where it landed. A span cannot be wrong about its own text, because nobody ever
computed it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

VOORNAMEN = ["Janine", "Pieter", "Fatima", "Bart", "Neeltje", "Ahmed", "Willemijn",
             "Joris", "Soraya", "Hendrik", "Lieke", "Youssef", "Marieke", "Ton"]
ACHTERNAMEN = ["van Dijk", "Bakker", "de Vries", "El Amrani", "Jansen", "Visser",
               "van der Meer", "Koster", "Smit", "de Groot", "Peters", "Bos"]
STEDEN = ["Nijmegen", "Arnhem", "Wijchen", "Beuningen", "Elst", "Zevenaar"]
STRATEN = ["Dorpsstraat", "Kerkstraat", "Molenweg", "Stationsplein", "Groenestraat"]


def bsn(rng: random.Random) -> str:
    """A number that passes the elfproef and belongs to nobody.

    An invalid BSN tests nothing: the detector rejects it and the corpus proves
    only that rejection works. So it must be valid — and therefore it must be
    generated rather than borrowed.
    """
    while True:
        digits = [rng.randint(0, 9) for _ in range(8)]
        weighted = sum(d * w for d, w in zip(digits, range(9, 1, -1)))
        last = weighted % 11
        if last > 9:                     # no ninth digit makes this one work
            continue
        total = weighted - last
        if total % 11 == 0 and any(digits):
            return "".join(map(str, digits)) + str(last)


def iban(rng: random.Random) -> str:
    """A Dutch IBAN passing mod-97, on a test bank code."""
    account = f"{rng.randrange(10**9, 10**10):010d}"
    # mod-97 is computed over the rearranged form: bank + account + country + "00"
    rearranged = f"INGB{account}NL00"
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    check = 98 - (int(numeric) % 97)
    return f"NL{check:02d}INGB{account}"


def postcode(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTVWXZ") for _ in range(2))
    return f"{rng.randrange(1000, 9999)} {letters}"


@dataclass
class Document:
    """Text plus the answer about that text."""

    doc_id: str
    topic: str
    text: str = ""
    entities: list[dict] = field(default_factory=list)
    # PII types present in the clear — what a combination measurement should see
    types: set[str] = field(default_factory=set)

    def lit(self, s: str) -> "Document":
        """Append text that is not PII."""
        self.text += s
        return self

    def pii(self, value: str, type_: str) -> "Document":
        """Append a value AND record where it landed."""
        start = len(self.text)
        self.text += value
        self.entities.append({"start": start, "end": len(self.text), "type": type_})
        self.types.add(type_)
        return self

    def unlabelled(self, value: str, type_: str) -> "Document":
        """Append a value that carries a type but is NOT gold.

        For types no detector emits (GENDER, a bare year of birth). They belong
        in a combination measurement and not in a precision score, and conflating
        the two would charge the detector with missing what it never claimed to
        find.
        """
        self.text += value
        self.types.add(type_)
        return self

    def check(self) -> "Document":
        """Every span must be exactly the text at that offset.

        Cheap, and it is the one invariant the whole corpus rests on. A corpus
        that lies about its own answers is worse than no corpus.
        """
        for e in self.entities:
            if not (0 <= e["start"] < e["end"] <= len(self.text)):
                raise ValueError(f"{self.doc_id}: span out of range: {e}")
        spans = sorted((e["start"], e["end"]) for e in self.entities)
        for (_, prev_end), (start, _) in zip(spans, spans[1:]):
            if start < prev_end:
                raise ValueError(f"{self.doc_id}: overlapping spans at {start}")
        return self

    def gold(self) -> dict:
        return {"id": self.doc_id, "text": self.text, "entities": self.entities}
