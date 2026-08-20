"""Per-PII-type key scoping on the KeyProvider (add-per-type-keyed-reveal)."""
from __future__ import annotations

from wordsworth.keys import InMemoryKeyProvider, KeyProvider, StubKeyProvider


def test_still_satisfies_protocol():
    assert isinstance(InMemoryKeyProvider(), KeyProvider)
    assert isinstance(StubKeyProvider("pw"), KeyProvider)


def test_distinct_scopes_have_distinct_active_keys():
    kp = InMemoryKeyProvider()
    person = kp.current_key(scope="PERSON")
    bsn = kp.current_key(scope="BSN")
    assert person.id != bsn.id
    assert person.material != bsn.material
    # stable within a scope
    assert kp.current_key(scope="PERSON").id == person.id


def test_default_scope_is_its_own_scope():
    kp = InMemoryKeyProvider()
    g = kp.current_key()
    assert kp.current_key().id == g.id          # stable
    assert kp.current_key(scope="PERSON").id != g.id


def test_key_resolves_any_version_across_scopes():
    kp = InMemoryKeyProvider()
    p = kp.current_key(scope="PERSON")
    b = kp.current_key(scope="BSN")
    assert kp.key(p.id).material == p.material
    assert kp.key(b.id).material == b.material


def test_rotate_is_scoped():
    kp = InMemoryKeyProvider()
    p0 = kp.current_key(scope="PERSON")
    b0 = kp.current_key(scope="BSN")
    p1 = kp.rotate(scope="PERSON")
    assert p1.id != p0.id
    assert kp.current_key(scope="PERSON").id == p1.id     # new active for PERSON
    assert kp.current_key(scope="BSN").id == b0.id         # BSN untouched
    assert kp.key(p0.id).material == p0.material           # old version resolvable


def test_stub_ignores_scope():
    sp = StubKeyProvider("pw")
    assert sp.current_key(scope="PERSON").id == sp.current_key(scope="BSN").id
