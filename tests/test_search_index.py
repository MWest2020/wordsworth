from wordsworth.search_index import InMemoryIndex, SearchIndex


def test_in_memory_satisfies_protocol():
    assert isinstance(InMemoryIndex(), SearchIndex)


def test_index_and_search_returns_doc():
    idx = InMemoryIndex()
    idx.index("d1", "de gemeente Haarlem besluit over parkeren", "k1")
    hits = idx.search("parkeren")
    assert [h.document_id for h in hits] == ["d1"]
    assert hits[0].object_key == "k1"


def test_stronger_match_ranks_higher():
    idx = InMemoryIndex()
    idx.index("weak", "parkeren", "a")
    idx.index("strong", "parkeren parkeren vergunning parkeren", "b")
    hits = idx.search("parkeren vergunning")
    assert [h.document_id for h in hits][0] == "strong"


def test_reindex_same_id_does_not_duplicate():
    idx = InMemoryIndex()
    idx.index("d1", "eerste versie", "k")
    idx.index("d1", "tweede versie", "k")
    hits = idx.search("versie")
    assert len(hits) == 1
