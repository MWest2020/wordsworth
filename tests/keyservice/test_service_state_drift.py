"""design.md "Service-only state": ``service_state`` is one table for state
that is neither copied from wordsworth nor derived from ``access_audit``.
Next to ``tests/keyservice/test_drift.py`` (the copied-table checker), this
file pins ``service_state``'s own shape and catches a counter or window
column that leaked onto any other table."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table

import wordsworth.models as wordsworth_models
from wordsworth.keyservice import state as keyservice_state
from wordsworth.keyservice.models import KeyServiceBase

from .test_drift import _COPIED_PAIRS

#: design.md "Service-only state": every table ``KeyServiceBase.metadata``
#: creates that is not one of ``_COPIED_PAIRS``' copies.
_SERVICE_OWN_TABLES = frozenset({
    "known_documents", "document_tokens", "access_audit", "service_state",
})

#: A column named like this, outside ``service_state``, is counter or
#: rate-limit/window state that escaped its one home.
_SUSPECT_COLUMN_NAMES = frozenset({
    "counter", "count", "tokens", "window_start", "refusals"})


def suspect_columns(tables) -> list[str]:
    """``table.column`` for every column named like a counter or window, on
    any table other than ``service_state``. Empty means none leaked."""
    return [f"{t.name}.{c.name}" for t in tables if t.name != "service_state"
            for c in t.columns if c.name in _SUSPECT_COLUMN_NAMES]


def test_service_state_has_exactly_its_columns():
    columns = {c.name: (type(c.type).__name__, c.nullable)
               for c in keyservice_state.ServiceState.__table__.columns}
    assert columns == {
        "kind": ("String", False),
        "key": ("String", False),
        "counter": ("BigInteger", False),
        "data": ("JSONB", True),
        "updated_at": ("DateTime", False),
    }
    pk = {c.name for c in keyservice_state.ServiceState.__table__.primary_key.columns}
    assert pk == {"kind", "key"}


def test_every_table_is_a_copy_or_one_of_the_services_own():
    copied_names = {copy.name for _, copy in _COPIED_PAIRS}
    all_names = set(KeyServiceBase.metadata.tables)
    assert all_names - copied_names - _SERVICE_OWN_TABLES == set()


def test_checker_catches_a_counter_column_outside_service_state():
    meta = MetaData()
    offender = Table("known_documents", meta, Column("id", String), Column("counter", Integer))
    assert suspect_columns([offender]) == ["known_documents.counter"]


def test_checker_catches_a_window_column_outside_service_state():
    meta = MetaData()
    offender = Table("document_tokens", meta, Column("token", String),
                      Column("window_start", String))
    assert suspect_columns([offender]) == ["document_tokens.window_start"]


def test_no_suspect_column_outside_service_state_today():
    assert suspect_columns(KeyServiceBase.metadata.tables.values()) == []


def test_service_state_is_absent_from_wordsworth_metadata():
    assert "service_state" not in wordsworth_models.Base.metadata.tables


def test_state_module_never_names_access_audit():
    source = Path(keyservice_state.__file__).read_text()
    assert "access_audit" not in source
