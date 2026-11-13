# SPDX-License-Identifier: MIT
"""The search page shows why a result matched (search-matching-passage): the
closest passage of the first ten hits, from the stored text, words marked, a
reason; the ranking's order; today's fragments and a notice when it cannot."""
from __future__ import annotations

import html
import re

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.dossiers import add, ensure
from wordsworth.hybrid import hybrid_search
from wordsworth.models import DocumentText
from wordsworth.passages import embed_passages
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex, SearchUnavailable

KEYS = {"s3cret": "mark"}
THEMES = (("geweigerd", "afgewezen", "afkeuring", "weiger"), ("parkeer", "fiets"))


class Embedder:
    """Meaning by theme: a text about refusing lies close to a question about
    refusing, shared words or not. ``fail_after`` calls, it is gone."""

    def __init__(self, fail_after: int | None = None):
        self.calls, self.fail_after = 0, fail_after

    def embed(self, texts):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ConnectionError("embedder unreachable")
        return [[1.0 if any(w in t.lower() for w in ws) else 0.0 for ws in THEMES]
                + [0.1] for t in texts]


def _words(n, prefix="regel"):
    return " ".join(f"{prefix}{i}" for i in range(n))


ANSWER = (_words(300) + " De aanvraag voor de dakkapel is geweigerd omdat het"
          " bouwplan te hoog is. " + _words(40, "slot"))
SEMANTIC = "De aanvraag is afgewezen omdat het bouwplan niet voldoet."


def seed(session_factory, index, texts: dict, passages=True) -> dict:
    """Index ``texts`` in dossier "zaak". ``passages``: True, False, or name -> vectors."""
    ids = {}
    with session_factory() as s:
        d = ensure(s, "zaak")
        s.flush()
        for name, text in texts.items():
            doc = register(s, f"documents/{name}", filename=f"{name}.pdf")
            add(s, d.id, doc.id, actor="test")
            s.merge(DocumentText(document_id=doc.id, anonymized_text=text))
            vecs = (passages.get(name) if isinstance(passages, dict)
                    else embed_passages(Embedder(), text) if passages else None)
            index.index(str(doc.id), text, f"documents/{name}",
                        vector=Embedder().embed([text])[0], dossiers=[str(d.id)],
                        passages=vecs)
            ids[name] = str(doc.id)
        s.commit()
    return ids


def page(session_factory, index, embedder=Embedder(), **params) -> str:
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index, embedder=embedder),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/console/search", params={"dossier": "zaak", **params})
    assert r.status_code == 200
    return r.text


def shown_passages(body: str) -> list[str]:
    raw = re.findall(r'<div class="note passage"[^>]*>(.*?)</div>', body, re.S)
    return [html.unescape(re.sub(r"</?mark>", "", p)).strip("…") for p in raw]


def order(body: str) -> list[str]:
    return re.findall(r'href="/console/documents/([0-9a-f-]{36})"', body)


class RecordingIndex(InMemoryIndex):
    def __init__(self, fail=False):
        super().__init__()
        self.asked, self.fail = [], fail

    def passages_of(self, ids):
        self.asked.append(list(ids))
        if self.fail:
            raise SearchUnavailable("search index unreachable: ConnectionError")
        return super().passages_of(ids)


def test_the_closest_passage_is_shown_as_it_stands_in_the_stored_text(session_factory):
    index = InMemoryIndex()
    seed(session_factory, index, {"besluit": ANSWER})
    body = page(session_factory, index, q="Waarom is de dakkapel geweigerd?")
    [shown] = shown_passages(body)
    assert shown in ANSWER and "dakkapel is geweigerd" in shown
    assert "<mark>dakkapel</mark>" in body and "<mark>geweigerd</mark>" in body
    assert "komt overeen op woorden en betekenis" in body
    # the score is a tooltip on the link, no longer a column of its own
    assert re.search(r'<a href="/console/documents/[0-9a-f-]{36}" title="score [0-9.]+">',
                     body)
    assert '<span class="state">' not in body


def test_a_semantic_match_says_meaning_and_marks_nothing(session_factory):
    index = InMemoryIndex()
    seed(session_factory, index, {"weigering": SEMANTIC})
    body = page(session_factory, index, q="Redenen tot afkeuring?")
    assert shown_passages(body) == [SEMANTIC]
    assert "komt overeen op betekenis" in body and "<mark>" not in body


def test_a_count_mismatch_and_no_vectors_show_todays_fragment(session_factory):
    index = InMemoryIndex()
    seed(session_factory, index, {"scheef": ANSWER, "kaal": SEMANTIC},
         passages={"scheef": [[1.0, 0.0, 0.1]], "kaal": None})
    body = page(session_factory, index, q="Waarom is de dakkapel geweigerd?")
    assert shown_passages(body) == []
    assert "komt overeen" not in body
    assert "dakkapel is geweigerd" in body      # today's fragments…
    assert "De aanvraag is afgewezen" in body
    assert "niet beschikbaar" not in body       # …and not an index outage


def test_an_index_that_fails_on_passages_keeps_the_results_and_says_so(session_factory):
    index = RecordingIndex(fail=True)
    seed(session_factory, index, {"besluit": ANSWER})
    body = page(session_factory, index, q="Waarom is de dakkapel geweigerd?")
    assert len(index.asked) == 1
    assert "passages zijn nu niet beschikbaar" in body
    assert len(order(body)) == 1 and shown_passages(body) == []
    assert "dakkapel is geweigerd" in body   # today's fragment, around the word


def test_a_failing_second_embedding_keeps_the_results_and_says_so(session_factory):
    index = RecordingIndex()
    seed(session_factory, index, {"besluit": ANSWER})
    body = page(session_factory, index, embedder=Embedder(fail_after=1),
                q="Waarom is de dakkapel geweigerd?")
    assert index.asked == []
    assert "passages zijn nu niet beschikbaar" in body
    assert len(order(body)) == 1 and shown_passages(body) == []


def test_stored_markup_arrives_as_text(session_factory):
    text = "Over de dakkapel: <script>alert(1)</script> de vergunning is geweigerd."
    index = InMemoryIndex()
    seed(session_factory, index, {"script": text})
    body = page(session_factory, index, q="vergunning geweigerd")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<script>alert" not in body
    assert "<mark>vergunning</mark>" in body


def test_only_the_first_ten_hits_get_a_passage(session_factory):
    index = RecordingIndex()
    ids = seed(session_factory, index,
               {f"d{i:02}": f"De dakkapel nummer {i} is geweigerd." for i in range(13)})
    body = page(session_factory, index, q="dakkapel geweigerd", size=25)
    assert len(order(body)) == 13
    assert len(index.asked) == 1 and index.asked[0] == order(body)[:10]
    assert len(shown_passages(body)) == 10
    assert set(order(body)) == set(ids.values())


def test_a_keyword_search_says_words_and_reads_no_passages(session_factory):
    index = RecordingIndex()
    seed(session_factory, index, {"besluit": ANSWER})
    body = page(session_factory, index, embedder=None, q="dakkapel geweigerd")
    assert index.asked == []
    assert "komt overeen op woorden" in body and shown_passages(body) == []


def test_the_order_is_the_rankings_with_and_without_passages(session_factory):
    texts = {"besluit": ANSWER, "weigering": SEMANTIC,
             "parkeren": "Een notitie over parkeren en de dakkapel van het stadhuis.",
             "fietsen": "Fietsenstalling bij het stadhuis, geen dakkapel."}
    q = "Waarom is de dakkapel geweigerd?"
    met = InMemoryIndex()
    seed(session_factory, met, texts)
    zonder = InMemoryIndex()                # the same documents, no passages
    for d, (text, key, vector) in met._docs.items():
        zonder.index(d, text, key, vector=vector, dossiers=sorted(met._dossiers[d]))
    with session_factory() as s:
        only = [str(ensure(s, "zaak").id)]
    orders = []
    for index in (met, zonder):
        body = page(session_factory, index, q=q)
        ranked = [h.document_id for h in hybrid_search(index, Embedder(), q, only=only)]
        assert order(body) == ranked
        orders.append(order(body))
    assert orders[0] == orders[1] and len(orders[0]) == 4 and not shown_passages(body)
