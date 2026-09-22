# SPDX-License-Identifier: MIT
"""De onderwerp-endpoints en de onderwerp-scope bij het zoeken (onderwerpen)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.dossiers import add, ensure
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex


def _corpus(session_factory, index):
    """Twee groepen in één dossier, allebei met het woord 'gemeente' erin zodat
    dezelfde zoekvraag in beide groepen treffers heeft."""
    with session_factory() as s:
        d = ensure(s, "zaak")
        s.flush()
        for kant, woord, vec in (("v", "vergunning kap boom", [1.0, 0.0, 0.0]),
                                 ("s", "subsidie cultuur regeling", [0.0, 1.0, 0.0])):
            for i in range(4):
                doc = register(s, f"documents/{kant}{i}")
                add(s, d.id, doc.id, actor="test")
                index.index(str(doc.id), f"gemeente {woord} {i}",
                            f"documents/{kant}{i}", vector=vec,
                            dossiers=[str(d.id)])
        s.commit()
        return d.id


def _client(session_factory, index):
    return TestClient(create_app(session_factory=session_factory,
                                 search_index=index))


def test_compute_then_list(session_factory):
    index = InMemoryIndex()
    dossier_id = _corpus(session_factory, index)
    client = _client(session_factory, index)

    r = client.post(f"/dossiers/{dossier_id}/topics")
    assert r.status_code == 200
    body = r.json()
    assert len(body["topics"]) == 2
    assert body["seen"] == 8 and body["with_vector"] == 8
    assert body["without_topic"] == 0
    assert all(t["computed_at"] for t in body["topics"])

    weer = client.get(f"/dossiers/{dossier_id}/topics").json()
    assert {t["id"] for t in weer["topics"]} == {t["id"] for t in body["topics"]}
    # Een lijst zonder berekening is leeg, niet stiekem een verse berekening.
    assert weer["seen"] is None


def test_an_unknown_dossier_is_404(session_factory):
    from uuid import uuid4
    client = _client(session_factory, InMemoryIndex())
    assert client.post(f"/dossiers/{uuid4()}/topics").status_code == 404
    assert client.get(f"/dossiers/{uuid4()}/topics").status_code == 404


def test_renaming_through_the_api_keeps_the_computed_name(session_factory):
    index = InMemoryIndex()
    dossier_id = _corpus(session_factory, index)
    client = _client(session_factory, index)
    topic = client.post(f"/dossiers/{dossier_id}/topics").json()["topics"][0]

    r = client.patch(f"/topics/{topic['id']}", json={"name": "Kapvergunningen"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Kapvergunningen"
    assert body["computed_name"] == topic["computed_name"]

    leeg = client.patch(f"/topics/{topic['id']}", json={"name": ""}).json()
    assert leeg["name"] == topic["computed_name"]
    assert leeg["given_name"] is None


def test_a_topic_narrows_the_search(session_factory):
    index = InMemoryIndex()
    dossier_id = _corpus(session_factory, index)
    client = _client(session_factory, index)
    topics = client.post(f"/dossiers/{dossier_id}/topics").json()["topics"]

    breed = client.get("/search", params={"q": "gemeente", "dossier": "zaak",
                                          "size": 50}).json()["hits"]
    assert len(breed) == 8

    per_onderwerp = []
    for t in topics:
        smal = client.get("/search", params={"q": "gemeente", "dossier": "zaak",
                                             "size": 50, "topic": t["id"]}).json()
        assert smal["topic"] == t["id"]
        per_onderwerp.append([h["document_id"] for h in smal["hits"]])
        assert len(smal["hits"]) == t["document_count"]

    samen = [d for lijst in per_onderwerp for d in lijst]
    assert sorted(samen) == sorted(h["document_id"] for h in breed)
    assert not set(per_onderwerp[0]) & set(per_onderwerp[1])


def test_a_topic_does_not_change_the_order(session_factory):
    """De belofte van deze change. Documenten die in beide uitslagen staan,
    staan onderling in dezelfde volgorde -- een onderwerp versmalt, het
    herschikt niet.

    Met verschillende scores, anders is 'dezelfde volgorde' gratis.
    """
    index = InMemoryIndex()
    with session_factory() as s:
        d = ensure(s, "zaak")
        s.flush()
        # Aflopend aantal treffers op 'gemeente' -> aflopende score.
        for i in range(6):
            doc = register(s, f"documents/d{i}")
            add(s, d.id, doc.id, actor="test")
            index.index(str(doc.id), ("gemeente " * (6 - i)) + f"vergunning {i}",
                        f"documents/d{i}",
                        vector=[1.0, 0.0] if i % 2 else [0.0, 1.0],
                        dossiers=[str(d.id)])
        s.commit()
        dossier_id = d.id
    client = _client(session_factory, index)
    topics = client.post(f"/dossiers/{dossier_id}/topics",
                         ).json()["topics"]

    breed = [h["document_id"] for h in client.get(
        "/search", params={"q": "gemeente", "dossier": "zaak", "size": 50}
    ).json()["hits"]]
    assert len(breed) == 6
    for t in topics:
        smal = [h["document_id"] for h in client.get(
            "/search", params={"q": "gemeente", "dossier": "zaak", "size": 50,
                               "topic": t["id"]}).json()["hits"]]
        assert smal == [d for d in breed if d in set(smal)], (
            "de volgorde verschoof binnen het onderwerp")
