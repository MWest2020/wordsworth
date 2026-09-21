# SPDX-License-Identifier: MIT
"""ARI en purity (onderwerpen): de getallen waarmee een indeling te toetsen is."""
from wordsworth.eval.metrics import adjusted_rand_index, purity


WAARHEID = {"a": "x", "b": "x", "c": "y", "d": "y"}


def test_a_perfect_grouping_is_one():
    gevonden = {"a": "1", "b": "1", "c": "2", "d": "2"}
    assert adjusted_rand_index(WAARHEID, gevonden) == 1.0
    assert purity(WAARHEID, gevonden) == 1.0


def test_names_do_not_have_to_match():
    """Een indeling is een partitie, geen naamgeving. Dat de berekende groep
    anders heet dan het bekende onderwerp mag niets uitmaken."""
    assert adjusted_rand_index(WAARHEID, {"a": "z", "b": "z", "c": "q",
                                          "d": "q"}) == 1.0


def test_everything_in_one_group_scores_zero_not_high():
    """Waarom de ARI en niet de kale Rand-index: alles op één hoop is de
    indeling die niets zegt, en die hoort geen hoog cijfer te krijgen.

    Purity geeft hier wél 0.5 — daarom staan ze naast elkaar.
    """
    alles = {d: "1" for d in WAARHEID}
    assert adjusted_rand_index(WAARHEID, alles) == 0.0
    assert purity(WAARHEID, alles) == 0.5


def test_exactly_wrong_is_negative():
    gekruist = {"a": "1", "b": "2", "c": "1", "d": "2"}
    assert adjusted_rand_index(WAARHEID, gekruist) < 0


def test_documents_without_a_group_are_left_out_not_counted_wrong():
    """Een document dat geen onderwerp kreeg is een ander getal. Meetellen als
    fout zou de indeling straffen voor iets dat apart gerapporteerd wordt."""
    deel = {"a": "1", "b": "1", "c": "2"}
    assert adjusted_rand_index(WAARHEID, deel) == 1.0
    assert purity(WAARHEID, deel) == 1.0


def test_too_little_to_say_anything():
    assert adjusted_rand_index({"a": "x"}, {"a": "1"}) == 0.0
    assert purity({}, {}) == 0.0
