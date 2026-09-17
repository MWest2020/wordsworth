# SPDX-License-Identifier: MIT
"""Sets of PII types that identify a person together, while none does alone.

Every value is judged on its own today. A record like "female, born 1978,
postcode 6541 EX, role X" therefore passes through untouched: not one of those
four is a direct identifier, and together they often name exactly one person.

That is the classic quasi-identifier, and it is why "we removed the names" has
not been a valid claim for thirty years.

Three things this module deliberately does NOT do.

It does not decide which combinations identify. That depends on the population,
the sector and the context, and it is the controller's call — a tool that decides
it for them is wrong in a way nobody notices until it matters.

It does not compute k-anonymity. Answering "how many people share this
combination" needs a population reference this system does not have. An invented
k reads as rigour and is worse than no k at all.

It does not refuse. A profile that leaves a declared combination in the clear
gets a finding, not a rejection. A tool that refuses on its own judgement teaches
people to route around it, and then it protects nothing.
"""
from __future__ import annotations

from dataclasses import dataclass


class CombinationError(ValueError):
    """A declaration that cannot be acted on."""


@dataclass(frozen=True)
class Combination:
    """PII types that identify together, and why.

    ``reason`` is required on purpose. A bare list of types is a rule nobody can
    review: in a year, the only way to judge whether it still holds is to know
    what it was for. Requiring prose costs one sentence now and saves the
    argument later.
    """

    types: frozenset[str]
    reason: str

    def __post_init__(self) -> None:
        if len(self.types) < 2:
            raise CombinationError(
                "a combination needs at least two types — one type that identifies "
                "on its own is a direct identifier, not a combination")
        if not self.reason or not self.reason.strip():
            raise CombinationError(
                "a combination needs a reason: which population does this narrow "
                "to one person, and why")


def parse(declarations: list[dict]) -> list[Combination]:
    """Read declarations as they appear in a profile."""
    out = []
    for d in declarations or []:
        types = d.get("types") or []
        out.append(Combination(frozenset(t.upper() for t in types),
                               d.get("reason", "")))
    return out


def unbroken(combination: Combination, pseudonymised: set[str]) -> bool:
    """Does this combination survive whatever is being pseudonymised?

    Breaking it is the useful state, and breaking ONE member is enough: the
    combination identifies only while all its parts line up. Hence a yes/no and
    not a score — there is nothing here to grade.

    Note what is NOT measured: whether those types actually occur in the data.
    A profile knows which columns it handles, not what stands in the others. The
    finding is "this profile breaks combination C nowhere", not "combination C
    occurs in this file". The first is a property of the profile and therefore
    checkable; the second needs the data and belongs to measurement.
    """
    types = {t.upper() for t in combination.types}
    return not (types & {t.upper() for t in pseudonymised})


def findings(combinations: list[Combination],
             pseudonymised: set[str]) -> list[Combination]:
    """Every declared combination that nothing here breaks."""
    return [c for c in combinations if unbroken(c, pseudonymised)]
