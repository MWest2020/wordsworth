# SPDX-License-Identifier: MIT
"""`transit.transit_factory` (`originals-ingest-seam`, task 2.1): one
``OpenBaoTransit`` per KEK name, shared across callers. No network --
``OpenBaoTransit`` touches ``httpx`` only on ``wrap``/``unwrap``, never at
construction, but ``httpx.post`` is monkeypatched to fail loudly anyway so a
regression here cannot silently reach the network."""
import httpx
import pytest

from wordsworth.transit import transit_factory


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("transit_factory must not touch the network")

    monkeypatch.setattr(httpx, "post", boom)


def test_same_kek_name_returns_the_same_client():
    transit_for = transit_factory("http://openbao:8200", "token")
    assert transit_for("kek-a") is transit_for("kek-a")


def test_different_kek_names_return_different_clients_with_their_own_kek():
    transit_for = transit_factory("http://openbao:8200", "token")
    a, b = transit_for("kek-a"), transit_for("kek-b")
    assert a is not b
    assert a._kek == "kek-a"
    assert b._kek == "kek-b"


def test_two_factories_do_not_share_a_cache():
    a = transit_factory("http://openbao:8200", "token")("kek-a")
    b = transit_factory("http://openbao:8200", "token")("kek-a")
    assert a is not b


# --- Task 2.2's proof: OpenBaoTransit( is only ever built in transit.py ----

def test_openbaotransit_is_constructed_only_in_transit_py():
    import pathlib

    src = pathlib.Path(__file__).resolve().parent.parent / "src" / "wordsworth"
    hits = []
    for path in src.rglob("*.py"):
        if "OpenBaoTransit(" in path.read_text():
            hits.append(path.name)
    assert hits == ["transit.py"]
