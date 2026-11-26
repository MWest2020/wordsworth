"""design.md "Reuse and imports", rule 1: KeyServiceBase.metadata contains no
wordsworth table, and the service's init creates only its own tables."""
from __future__ import annotations

from sqlalchemy import inspect

import wordsworth.document_keys  # noqa: F401 -- registers on wordsworth.models.Base
import wordsworth.models as wordsworth_models
from wordsworth.keyservice import models_access  # noqa: F401
from wordsworth.keyservice.db import init_schema
from wordsworth.keyservice.models import KeyServiceBase


def test_table_objects_are_disjoint():
    service_tables = set(KeyServiceBase.metadata.tables.values())
    wordsworth_tables = set(wordsworth_models.Base.metadata.tables.values())
    assert service_tables.isdisjoint(wordsworth_tables)


def test_same_names_two_databases_is_fine():
    # Same table NAME in both metadatas is expected for the copied tables
    # (key_vault, pii_mappings, grants, roles, group_roles,
    # key_lifecycle_events, rate_limit_buckets) -- it is the same Table
    # OBJECT that must never happen (test above), not the name.
    service_names = set(KeyServiceBase.metadata.tables)
    wordsworth_names = set(wordsworth_models.Base.metadata.tables)
    assert service_names & wordsworth_names


def test_init_creates_only_service_tables(keyservice_session_factory, keyservice_database_url):
    from wordsworth.keyservice.db import make_engine

    engine = make_engine(keyservice_database_url)
    created = set(inspect(engine).get_table_names())
    # Exact match against the service's own tables -- if any wordsworth-only
    # table (documents, audit_records, ...) had leaked in, this would fail.
    assert created == set(KeyServiceBase.metadata.tables)


def test_second_init_is_a_noop(keyservice_database_url):
    from wordsworth.keyservice.db import make_engine

    engine = make_engine(keyservice_database_url)
    init_schema(engine)
    init_schema(engine)  # must not raise
    assert set(inspect(engine).get_table_names()) == set(KeyServiceBase.metadata.tables)
