"""add-pii-categories-and-ppl: registry + PPL expansion (pure)."""
import logging

from wordsworth import pii_categories as pc


def test_known_types_resolve():
    assert pc.category_of("GEZONDHEID") == "c2"
    assert pc.legal_basis_of("gezondheid") == "Art. 9"
    assert pc.ppl_min_of("GEZONDHEID") == 2
    assert pc.category_of("BSN") == "c1" and pc.ppl_min_of("PERSON") == 1
    assert pc.category_of("STRAFRECHTELIJK") == "c3" and pc.ppl_min_of("CRIMINAL") == 3


def test_unknown_type_is_c1_and_warned_once(caplog):
    pc._warned.discard("ZZ_UNKNOWN")
    with caplog.at_level(logging.WARNING, logger="wordsworth.pii_categories"):
        assert pc.category_of("zz_unknown") == "c1"
        assert pc.category_of("ZZ_UNKNOWN") == "c1"
    assert sum("ZZ_UNKNOWN" in r.message for r in caplog.records) == 1


def test_ppl_expansion_is_cumulative():
    p0, p1, p2, p3 = (pc.types_for_ppl(n) for n in range(4))
    assert p0 == set()
    assert "PERSON" in p1 and "GEZONDHEID" not in p1 and "STRAFRECHTELIJK" not in p1
    assert p1 < p2 < p3
    assert "GEZONDHEID" in p2 and "STRAFRECHTELIJK" not in p2
    assert "STRAFRECHTELIJK" in p3
    assert "ZZ_UNKNOWN" not in p3  # never granted implicitly by a level


def test_ppl_bounds():
    import pytest
    with pytest.raises(ValueError):
        pc.types_for_ppl(4)


def test_ppl_of_types_roundtrip():
    for n in range(4):
        assert pc.ppl_of_types(pc.types_for_ppl(n)) == n
    assert pc.ppl_of_types({"PERSON"}) is None


def test_group_by_basis_partitions():
    types = {"PERSON", "gezondheid", "STRAFRECHTELIJK", "BSN"}
    g = pc.group_by_basis(types)
    assert g == {"Art. 6": ["BSN", "PERSON"], "Art. 9": ["GEZONDHEID"],
                 "Art. 10": ["STRAFRECHTELIJK"]}
    assert sum(len(v) for v in g.values()) == len(types)


def test_counts_by_category():
    assert pc.counts_by_category({"bsn": 2, "gezondheid": 1, "email": 0}) == {
        "c1": 2, "c2": 1, "c3": 0}
