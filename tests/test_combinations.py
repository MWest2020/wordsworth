# SPDX-License-Identifier: MIT
"""Combinations of PII types that identify together (identifying-combinations)."""
import pytest

from wordsworth import combinations
from wordsworth.datasets import Profile

GESLACHT_JAAR_POSTCODE = {
    "types": ["GENDER", "DATE", "POSTCODE"],
    "reason": "gender + year of birth + 4-digit postcode narrows a Dutch "
              "municipality to a handful of people; with the letters, often one",
}


def test_a_declaration_needs_two_types():
    with pytest.raises(combinations.CombinationError):
        combinations.parse([{"types": ["BSN"], "reason": "identifies alone"}])


def test_a_declaration_without_a_reason_is_refused():
    with pytest.raises(combinations.CombinationError):
        combinations.parse([{"types": ["GENDER", "DATE"], "reason": "  "}])


def test_breaking_one_member_breaks_the_combination():
    c, = combinations.parse([GESLACHT_JAAR_POSTCODE])
    assert combinations.unbroken(c, {"POSTCODE"}) is False
    assert combinations.unbroken(c, set()) is True
    # case of the declaration must not decide the answer
    assert combinations.unbroken(c, {"postcode"}) is False


def test_a_profile_that_breaks_a_combination_nowhere_is_reported():
    prof = Profile(columns={"naam": "PERSON"}, combinations=[GESLACHT_JAAR_POSTCODE])
    found = prof.unbroken_combinations()
    assert [sorted(c.types) for c in found] == [["DATE", "GENDER", "POSTCODE"]]
    assert "postcode" in found[0].reason


def test_a_profile_that_breaks_it_reports_nothing():
    prof = Profile(columns={"geboortedatum": "DATE"},
                   combinations=[GESLACHT_JAAR_POSTCODE])
    assert prof.unbroken_combinations() == []


def test_per_record_breaks_what_it_replaces():
    # per_record gives the selected columns ONE shared token instead of one
    # each, but it still replaces them. The mode must not change the answer.
    prof = Profile(columns={"geslacht": "GENDER", "postcode": "POSTCODE"},
                   mode="per_record", record_key=["geslacht", "postcode"],
                   combinations=[GESLACHT_JAAR_POSTCODE])
    assert prof.unbroken_combinations() == []


def test_a_bad_declaration_is_refused_when_the_profile_loads():
    with pytest.raises(ValueError):
        Profile(columns={"naam": "PERSON"},
                combinations=[{"types": ["GENDER"], "reason": "x"}])


def test_no_declarations_means_no_findings():
    assert Profile(columns={"naam": "PERSON"}).unbroken_combinations() == []
