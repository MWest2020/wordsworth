"""access_audit and key_lifecycle_events are append-only at the schema level
(design.md "Schema"): UPDATE and DELETE raise."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from wordsworth.keyservice.models_access import AccessAudit, KeyLifecycleEvent


def _row(model):
    now = datetime.now(timezone.utc)
    if model is AccessAudit:
        return AccessAudit(ts=now, event="opened", service_caller="ingest",
                           prev_hash="0" * 64, hash="1" * 64)
    return KeyLifecycleEvent(ts=now, action="rotation", actor="ops",
                             prev_hash="0" * 64, hash="1" * 64)


@pytest.mark.parametrize("model,table", [
    (AccessAudit, "access_audit"),
    (KeyLifecycleEvent, "key_lifecycle_events"),
])
def test_update_raises(keyservice_session_factory, model, table):
    with keyservice_session_factory() as session:
        row = _row(model)
        session.add(row)
        session.commit()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(f"UPDATE {table} SET hash = 'x' WHERE seq = :seq"),
                            {"seq": row.seq})


@pytest.mark.parametrize("model,table", [
    (AccessAudit, "access_audit"),
    (KeyLifecycleEvent, "key_lifecycle_events"),
])
def test_delete_raises(keyservice_session_factory, model, table):
    with keyservice_session_factory() as session:
        row = _row(model)
        session.add(row)
        session.commit()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(f"DELETE FROM {table} WHERE seq = :seq"), {"seq": row.seq})
