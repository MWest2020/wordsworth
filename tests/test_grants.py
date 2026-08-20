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
    g = InMemoryGrantStore().issue("R", ["PERSON", "email"], actor="mark")
    assert authorize(g, None, {"PERSON", "BSN"}, NOW) == {"PERSON"}
    assert authorize(g, None, {"EMAIL"}, NOW) == {"EMAIL"}   # allowed_types upper-cased
    assert authorize(g, None, {"BSN"}, NOW) == set()


def test_revoked_authorizes_nothing():
    s = InMemoryGrantStore()
    g = s.issue("R", ["PERSON"], actor="mark")
    s.revoke(g.grant_id, actor="mark")
    assert authorize(g, None, {"PERSON"}, NOW) == set()


def test_expired_authorizes_nothing():
    g = InMemoryGrantStore().issue("R", ["PERSON"], actor="mark", expires_at=NOW)
    assert authorize(g, None, {"PERSON"}, NOW) == set()                    # now >= expiry
    assert authorize(g, None, {"PERSON"}, NOW - timedelta(seconds=1)) == {"PERSON"}


def test_document_scope():
    s = InMemoryGrantStore()
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    g = s.issue("R", ["PERSON"], actor="mark", document_id=d1)
    assert authorize(g, d1, {"PERSON"}, NOW) == {"PERSON"}
    assert authorize(g, d2, {"PERSON"}, NOW) == set()


def test_global_grant_authorizes_any_document():
    g = InMemoryGrantStore().issue("R", ["PERSON"], actor="mark")  # document_id None
    assert authorize(g, uuid.uuid4(), {"PERSON"}, NOW) == {"PERSON"}


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

    # and the revoked grant now authorizes nothing
    assert authorize(s.get(g.grant_id), None, {"PERSON"}, NOW) == set()


def test_revoke_is_idempotent():
    s = InMemoryGrantStore()
    g = s.issue("R", ["PERSON"], actor="mark")
    s.revoke(g.grant_id, "mark")
    s.revoke(g.grant_id, "mark")  # no error
    assert s.get(g.grant_id).status == "revoked"
