# SPDX-License-Identifier: MIT
"""The passage rule of candidate 2 (long-documents-rank-fairly)."""
from wordsworth.eval.passages import best_passage_scores, split


def _text(n):
    return " ".join(f"w{i}" for i in range(n))


def test_a_short_text_is_one_passage_and_an_empty_one_none():
    assert split(_text(5), words=4, stride=3) == ["w0 w1 w2 w3", "w1 w2 w3 w4"]
    assert split(_text(3), words=4, stride=3) == ["w0 w1 w2"]
    assert split("   ", words=4, stride=3) == []


def test_windows_overlap_and_cover_every_word():
    text = _text(23)
    parts = split(text, words=10, stride=7)
    assert parts[0].split()[0] == "w0" and parts[-1].split()[-1] == "w22"
    covered = {w for p in parts for w in p.split()}
    assert covered == set(text.split())
    assert all(len(p.split()) == 10 for p in parts)
    # consecutive windows share words - STRIDE words
    assert len(set(parts[0].split()) & set(parts[1].split())) == 3


def test_a_document_scores_by_its_best_passage():
    q = [1.0, 0.0]
    scores = best_passage_scores(q, {"long": [[0.0, 1.0], [0.0, 1.0], [1.0, 0.1]],
                                     "short": [[0.7, 0.7]]})
    assert scores["long"] > scores["short"]
