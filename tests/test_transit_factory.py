# SPDX-License-Identifier: MIT
"""`transit.transit_factory` (task 2.1): one `OpenBaoTransit` per KEK name,
cached in the closure, no network at construction time."""
import httpx
import pytest

from wordsworth.transit import OpenBaoTransit, transit_factory


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("transit_factory must not touch the network")

    monkeypatch.setattr(httpx, "post", _boom)


def test_same_kek_name_returns_the_same_client():
    transit_for = transit_factory("http://bao:8200", "token")
    assert transit_for("wordsworth") is transit_for("wordsworth")


def test_two_kek_names_return_two_clients_each_with_its_own_kek():
    transit_for = transit_factory("http://bao:8200", "token")
    a = transit_for("kek-a")
    b = transit_for("kek-b")
    assert a is not b
    assert isinstance(a, OpenBaoTransit) and isinstance(b, OpenBaoTransit)
    assert a._kek == "kek-a"
    assert b._kek == "kek-b"


def test_two_factories_do_not_share_a_cache():
    a = transit_factory("http://bao:8200", "token")("wordsworth")
    b = transit_factory("http://bao:8200", "token")("wordsworth")
    assert a is not b
