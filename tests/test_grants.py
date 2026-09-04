"""Reveal grants — pure/local (no DB) (add-reveal-grants)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from wordsworth.grants import (
    GrantStore,
    InMemoryGrantStore,
    authorize,
    issue_grant,
    revoke_grant,
)
from wordsworth.key_audit import (
    GRANT_ISSUED_ACTION,
    GRANT_REVOKED_ACTION,
    STREAM,
    JsonlKeyLifecycleAudit,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_store_satisfies_protocol():
    assert isinstance(InMemoryGrantStore(), GrantStore)


def test_authorize_intersects_requested_with_allowed():
    # Scoped to a document so the intersection is what is under test, not the
    # global-grant gate (which is closed by default).
    d = uuid.uuid4()
    g = InMemoryGrantStore().issue("R", ["PERSON", "email"], actor="mark",
                                   document_id=d)
    assert authorize(g, d, {"PERSON", "BSN"}, NOW) == {"PERSON"}
    assert authorize(g, d, {"EMAIL"}, NOW) == {"EMAIL"}   # allowed_types upper-cased
    assert authorize(g, d, {"BSN"}, NOW) == set()


def test_revoked_authorizes_nothing():
    s = InMemoryGrantStore()
    d = uuid.uuid4()
    g = s.issue("R", ["PERSON"], actor="mark", document_id=d)
    assert authorize(g, d, {"PERSON"}, NOW) == {"PERSON"}   # authorized before
    s.revoke(g.grant_id, actor="mark")
    assert authorize(g, d, {"PERSON"}, NOW) == set()


def test_expired_authorizes_nothing():
    d = uuid.uuid4()
    g = InMemoryGrantStore().issue("R", ["PERSON"], actor="mark", expires_at=NOW,
                                   document_id=d)
    assert authorize(g, d, {"PERSON"}, NOW) == set()                       # now >= expiry
    assert authorize(g, d, {"PERSON"}, NOW - timedelta(seconds=1)) == {"PERSON"}


def test_document_scope():
    s = InMemoryGrantStore()
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    g = s.issue("R", ["PERSON"], actor="mark", document_id=d1)
    assert authorize(g, d1, {"PERSON"}, NOW) == {"PERSON"}
    assert authorize(g, d2, {"PERSON"}, NOW) == set()


def test_global_grant_is_inert_unless_allowed():
    """An unscoped grant reveals on every document — a capability only available
    where the deployment allows it (harden-global-grant-gate)."""
    g = InMemoryGrantStore().issue("R", ["PERSON"], actor="mark")  # document_id None
    assert authorize(g, uuid.uuid4(), {"PERSON"}, NOW) == set()
    assert authorize(g, uuid.uuid4(), {"PERSON"}, NOW,
                     allow_global=True) == {"PERSON"}


def test_allowing_global_grants_does_not_widen_a_scoped_grant():
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    g = InMemoryGrantStore().issue("R", ["PERSON"], actor="mark", document_id=d1)
    assert authorize(g, d1, {"PERSON"}, NOW, allow_global=True) == {"PERSON"}
    assert authorize(g, d2, {"PERSON"}, NOW, allow_global=True) == set()


def test_issue_and_revoke_are_audited_without_key_material(tmp_path):
    s = InMemoryGrantStore()
    ka = JsonlKeyLifecycleAudit(tmp_path / "k.jsonl")
    g = issue_grant(s, ka, "R", ["PERSON", "EMAIL"], actor="mark")
    revoke_grant(s, ka, g.grant_id, actor="mark")

    events = ka.events()
    assert len(events) == 2
    issued, revoked = events
    assert issued["stage"] == STREAM and issued["action"] == GRANT_ISSUED_ACTION
    assert issued["grant_id"] == g.grant_id
    assert issued["recipient"] == "R"
    assert issued["allowed_types"] == ["PERSON", "EMAIL"]
    assert issued["actor"] == "mark"
    assert revoked["action"] == GRANT_REVOKED_ACTION and revoked["grant_id"] == g.grant_id
    # a grant is authorization only — no key/secret fields anywhere in the stream
    raw = (tmp_path / "k.jsonl").read_text(encoding="utf-8")
    assert "material" not in raw and "key_id" not in raw

    # and the revoked grant now authorizes nothing — allow_global so revocation,
    # not the global-grant gate, is what denies here
    assert authorize(s.get(g.grant_id), None, {"PERSON"}, NOW,
                     allow_global=True) == set()


def test_revoke_is_idempotent():
    s = InMemoryGrantStore()
    g = s.issue("R", ["PERSON"], actor="mark")
    s.revoke(g.grant_id, "mark")
    s.revoke(g.grant_id, "mark")  # no error
    assert s.get(g.grant_id).status == "revoked"
