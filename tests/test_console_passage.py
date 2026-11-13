# SPDX-License-Identifier: MIT
"""`console_passage.best`: which passage, which words, which reason.

Unit level: vectors are written by hand, so each test says exactly which
passage is closest. The console tests are in `test_console_search_passage.py`.
"""
import subprocess
from pathlib import Path

from wordsworth.console_passage import MEANING, WORDS_AND_MEANING, best
from wordsworth.passages import split_spans

SRC = Path(__file__).parent.parent / "src" / "wordsworth" / "console_passage.py"
NEAR, FAR = [1.0, 0.0], [0.0, 1.0]


def _filler(n, prefix="regel"):
    return " ".join(f"{prefix}{i}" for i in range(n))


def _shown(p):
    return "".join(s["text"] for s in p["segments"])


def _marked(p):
    return [s["text"] for s in p["segments"] if s["marked"]]


def test_the_second_passage_holds_the_answer():
    text = _filler(300) + " De aanvraag voor de dakkapel is geweigerd. " + _filler(40, "slot")
    spans = split_spans(text)
    assert len(spans) == 2
    p = best(text, [FAR, NEAR], NEAR, "Waarom is de dakkapel geweigerd?")
    assert p["span"] == spans[1]
    assert _shown(p) in text[spans[1][0]:spans[1][1]]
    assert p["reason"] == WORDS_AND_MEANING
    assert _marked(p) == ["dakkapel", "geweigerd"]


def test_a_passage_without_a_shared_word_matches_on_meaning():
    text = "De aanvraag is afgewezen omdat het bouwplan niet voldoet."
    p = best(text, [NEAR], NEAR, "Redenen tot afkeuring?")
    assert p["reason"] == MEANING
    assert _marked(p) == [] and p["words"] == []
    assert _shown(p) == text
    padded = best("  " + text + " \n", [NEAR], NEAR, "afkeuring")
    assert not padded["cut_before"] and not padded["cut_after"]


def test_word_start_case_insensitive_and_four_characters():
    text = "De vergunningen zijn verleend; de aanbesteding en gunning volgen."
    p = best(text, [NEAR], NEAR, "Vergunning de gunning?")
    # "Vergunning" marks "vergunningen"; "de" is too short; "gunning" counts
    # only where it starts a word, never inside "vergunningen".
    assert _marked(p) == ["vergunningen", "gunning"]
    assert p["words"] == ["gunning", "vergunningen"]
    q = best("De vergunning is verleend.", [NEAR], NEAR, "gunning de")
    assert _marked(q) == [] and q["reason"] == MEANING


def test_a_long_passage_is_trimmed_around_its_first_marked_word():
    text = _filler(189) + " het besluit tot weigering staat hier " + _filler(5, "eind")
    assert len(text.split()) == 200 and len(split_spans(text)) == 1
    p = best(text, [NEAR], NEAR, "weigering")
    shown = _shown(p)
    assert shown in text and len(shown) < len(text)
    assert "weigering" in _marked(p)
    assert p["cut_before"] and not p["cut_after"]
    assert not shown.startswith(" ") and not shown.endswith(" ")
    # the cut falls between words, not inside one
    start, end = p["shown"]
    assert text[start - 1].isspace() and (end == len(text) or text[end].isspace())


def test_nothing_marked_shows_the_opening_of_the_passage():
    text = _filler(200)
    p = best(text, [NEAR], NEAR, "dakkapel")
    assert p["shown"][0] == 0 and p["cut_after"] and not p["cut_before"]


def test_segments_join_to_the_shown_text_and_carry_no_markup():
    text = "Over de <script>alert(1)</script> vergunning <b>vet</b>."
    p = best(text, [NEAR], NEAR, "vergunning")
    start, end = p["shown"]
    assert _shown(p) == text[start:end]
    assert any("<script>alert(1)</script>" in s["text"] and not s["marked"]
               for s in p["segments"])
    assert all(set(s) == {"text", "marked"} for s in p["segments"])
    found = subprocess.run(["grep", "-n", r"Markup\|<mark", str(SRC)],
                           capture_output=True, text=True)
    assert found.stdout == ""


def test_a_count_mismatch_gives_no_passage():
    text = _filler(300)
    assert len(split_spans(text)) == 2
    assert best(text, [NEAR], NEAR, "regel5") is None
    assert best(text, [NEAR, FAR, FAR], NEAR, "regel5") is None
    assert best(text, [], NEAR, "regel5") is None
    assert best("", [], NEAR, "regel5") is None


def test_vectors_of_another_dimension_give_no_passage():
    """Indexed by another embedder: no comparison, and no 500 from `cosine`."""
    assert best("De aanvraag is afgewezen.", [[1.0, 0.0, 0.0]], NEAR, "aanvraag") is None
