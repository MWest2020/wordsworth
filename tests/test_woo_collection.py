# SPDX-License-Identifier: MIT
"""The rules that turn publisher records into a ranking collection.

Tested so they are rules and not judgment: the same file name gives the same
query on every run, and a name without a subject is skipped, not guessed.
"""
from wordsworth.eval.woo_collection import (query_from_decision, query_from_filename,
                                            reciprocal_rank, thirds)


def test_a_file_name_becomes_its_subject_words():
    assert query_from_filename(
        "0007_RE_WP_Echteld_Lienden_Verweerschrift_natuur_PRDF_11025011_2_msg_44684629_ff4556354c.pdf"
    ) == "echteld lienden verweerschrift natuur"
    assert query_from_filename("0000_Woo_besluit_80c7e0f9d4.pdf") == "woo besluit"


def test_a_name_without_a_subject_is_skipped():
    assert query_from_filename("0016_Image_3_jpg_44684226_d7ca15ec5b.pdf") is None
    assert query_from_filename("0029_image002_jpg_44684251_8b5f8e5c33.pdf") is None


def test_a_decision_url_becomes_its_title():
    assert query_from_decision(
        "https://open.gelderland.nl/woo-documenten/woo-besluit-over-ballonfiesta-barneveld2026-009291"
    ) == "woo besluit over ballonfiesta barneveld"


def test_thirds_are_equal_count_and_stable():
    lengths = {"a": 10, "b": 10, "c": 30, "d": 40, "e": 50, "f": 60}
    split = thirds(lengths)
    assert [split[k] for k in "abcdef"] == ["short", "short", "middle", "middle",
                                            "long", "long"]
    assert thirds(dict(reversed(list(lengths.items())))) == split


def test_reciprocal_rank():
    assert reciprocal_rank(["x", "y", "z"], {"y"}) == 0.5
    assert reciprocal_rank(["x"], {"q"}) == 0.0
