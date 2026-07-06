from datetime import datetime, timezone
from uuid import uuid4

import pytest

from wordsworth.hashing import GENESIS_HASH, canonical_content, compute_hash


def _args(**over):
    base = dict(
        document_id=uuid4(),
        from_state=None,
        to_state="registered",
        ts=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        step="register",
        payload={"a": 1, "b": 2},
    )
    base.update(over)
    return base


def test_canonical_is_deterministic():
    args = _args()
    assert canonical_content(**args) == canonical_content(**args)


def test_canonical_key_order_is_stable():
    doc, ts = uuid4(), datetime.now(timezone.utc)
    a = canonical_content(document_id=doc, from_state=None, to_state="x",
                          ts=ts, step="s", payload={"a": 1, "b": 2})
    b = canonical_content(document_id=doc, from_state=None, to_state="x",
                          ts=ts, step="s", payload={"b": 2, "a": 1})
    assert a == b


def test_timestamp_must_be_timezone_aware():
    with pytest.raises(ValueError):
        canonical_content(**_args(ts=datetime(2026, 7, 6, 12, 0)))


def test_hash_depends_on_prev_and_content():
    content = "content"
    assert compute_hash(GENESIS_HASH, content) == compute_hash(GENESIS_HASH, content)
    assert compute_hash(GENESIS_HASH, content) != compute_hash("other", content)
    assert compute_hash(GENESIS_HASH, "a") != compute_hash(GENESIS_HASH, "b")
