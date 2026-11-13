# SPDX-License-Identifier: MIT
"""`passages.split_spans`: the windows of `split`, as offsets into the text.

The console quotes ``text[s:e]`` of the stored text (search-matching-passage).
That is only honest if each span is the window `split` embedded: the invariant
below is the whole contract.
"""
import pytest

from wordsworth.passages import split, split_spans


def _same_windows(text, **kw):
    spans = split_spans(text, **kw)
    passages = split(text, **kw)
    assert len(spans) == len(passages)
    for (s, e), passage in zip(spans, passages):
        assert " ".join(text[s:e].split()) == passage
        # a span starts and ends on a word, never on whitespace
        assert not text[s].isspace() and not text[e - 1].isspace()
    return spans


def _words(n):
    return " ".join(f"w{i}" for i in range(n))


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_an_empty_text_has_no_spans(text):
    assert _same_windows(text) == []


def test_a_text_shorter_than_one_window_is_one_span():
    text = "  De aanvraag   is afgewezen.\n"
    assert _same_windows(text) == [(2, len(text) - 1)]


def test_the_tail_the_stride_steps_over_gets_its_own_span():
    # 9 tokens, windows of 4 every 3: starts 0 and 3, then the tail 5..9.
    text = _words(9)
    spans = _same_windows(text, words=4, stride=3)
    assert len(spans) == 3
    assert text[spans[-1][0]:spans[-1][1]] == "w5 w6 w7 w8"


def test_newlines_and_repeated_spaces_stay_in_the_span():
    text = "Eerste  regel\n\nmet   witruimte\tertussen " * 40
    spans = _same_windows(text, words=10, stride=7)
    assert any("\n\n" in text[s:e] for s, e in spans)


def test_the_default_window_on_a_long_text():
    text = "\n".join(_words(1000).split(" w5"))   # newlines scattered in
    _same_windows(text)
