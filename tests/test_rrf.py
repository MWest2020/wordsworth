from wordsworth.rrf import fuse_ranked_ids, reciprocal_rank_fusion


def test_doc_ranked_high_in_both_wins():
    fused = fuse_ranked_ids([["a", "b", "c"], ["a", "c", "b"]])
    assert fused[0] == "a"


def test_union_of_both_lists_is_covered():
    fused = fuse_ranked_ids([["a", "b"], ["c", "d"]])
    assert set(fused) == {"a", "b", "c", "d"}


def test_score_rewards_top_ranks():
    scores = reciprocal_rank_fusion([["a", "b"]])
    assert scores["a"] > scores["b"]


def test_appearing_in_both_beats_appearing_in_one():
    scores = reciprocal_rank_fusion([["a", "x"], ["a", "y"]])
    assert scores["a"] > scores["x"]
    assert scores["a"] > scores["y"]
