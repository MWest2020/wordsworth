"""Export helpers + the ranking-CSV endpoint — pure/local (no DB) (add-export)."""
from __future__ import annotations

import csv
import io
import zipfile

from fastapi.testclient import TestClient

from wordsworth.api import _anonymized_zip, _ranking_csv, create_app
from wordsworth.search_index import Hit, InMemoryIndex


def test_anonymized_zip_holds_only_the_given_texts():
    pairs = [("d1", "besluit [BSN:aaaa1111] over parkeren"),
             ("d2", "[PERSON:bbbb2222] woont in de straat")]
    zf = zipfile.ZipFile(io.BytesIO(_anonymized_zip(pairs)))
    assert set(zf.namelist()) == {"d1.txt", "d2.txt"}
    assert zf.read("d1.txt").decode() == pairs[0][1]
    assert "123456782" not in zf.read("d1.txt").decode()  # only de-identified text


def test_ranking_csv_is_ranked_with_a_header():
    rows = list(csv.reader(io.StringIO(_ranking_csv(
        [Hit("d2", 9.0, "k2"), Hit("d1", 3.0, "k1")]))))
    assert rows[0] == ["rank", "document_id", "score", "object_key"]
    assert rows[1][0] == "1" and rows[1][1] == "d2"
    assert rows[2][0] == "2" and rows[2][1] == "d1"


def test_export_ranking_endpoint_returns_ranked_csv():
    idx = InMemoryIndex()
    idx.index("d1", "parkeren in Haarlem", "k1")
    idx.index("d2", "iets over honden", "k2")
    client = TestClient(create_app(search_index=idx, rate_limiters={}))
    r = client.get("/export/ranking.csv", params={"query": "parkeren"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["rank", "document_id", "score", "object_key"]
    assert rows[1][1] == "d1"  # the matching document ranks first
