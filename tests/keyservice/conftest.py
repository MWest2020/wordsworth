"""Fixtures for the key service's own tests. Chained off the repo-wide
``tests/conftest.py`` (``database_url``, ``session_factory``): pytest loads
conftest files up the directory tree, so those fixtures (Docker-backed
PostgreSQL, skip-if-unavailable) are available here unchanged.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from sqlalchemy import text

from wordsworth.keyservice.db import init_schema, make_engine, make_session_factory
from wordsworth.keyservice.models import KeyServiceBase


class _PoisonedSettings:
    """Every attribute access raises -- design.md "Reuse and imports" rule 2:
    no service code path may read ``wordsworth.config.settings``."""

    def __getattr__(self, name):
        raise AssertionError(
            f"a key-service code path read wordsworth.config.settings.{name}")


@pytest.fixture(autouse=True)
def no_wordsworth_config(request, monkeypatch):
    """Replaces ``settings`` in ``wordsworth.config`` and in every already
    loaded ``wordsworth.*`` module that bound it by name (``from .config
    import settings``) with an object that raises on any attribute access.
    Scoped to this directory only (an autouse fixture in a subdirectory
    conftest applies to that subdirectory's tests, not wordsworth's own,
    which legitimately read ``config.settings`` everywhere).

    Skipped for a test that itself requests wordsworth's own
    ``session_factory`` fixture: that fixture builds a REAL wordsworth
    database (for a drift or isolation comparison) via
    ``wordsworth.db.make_engine``, which legitimately reads
    ``config.settings`` -- that is wordsworth's test infrastructure, not a
    key-service code path, and is not what rule 2 guards against."""
    if "session_factory" in request.fixturenames:
        yield
        return
    poison = _PoisonedSettings()
    monkeypatch.setattr("wordsworth.config.settings", poison)
    for name, module in list(sys.modules.items()):
        if not name.startswith("wordsworth") or name.startswith("wordsworth.keyservice"):
            continue
        if hasattr(module, "settings"):
            monkeypatch.setattr(module, "settings", poison)
    yield


@pytest.fixture(scope="session")
def keyservice_database_url(database_url):
    """A second private database, next to wordsworth's -- design.md "Tests".
    ``KEYSERVICE_TEST_DATABASE_URL`` wins when set; otherwise a throwaway
    database is created on the same server as ``database_url`` and dropped
    afterwards."""
    env_url = os.environ.get("KEYSERVICE_TEST_DATABASE_URL")
    if env_url:
        yield env_url
        return

    dbname = f"wordsworth_keyservice_test_{uuid.uuid4().hex[:8]}"
    admin_engine = make_engine(database_url)
    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin_engine.dispose()

    base = database_url.rsplit("/", 1)[0]
    yield f"{base}/{dbname}"

    admin_engine = make_engine(database_url)
    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # Every test's own engine (keyservice_session_factory) pools a
        # connection to this database and never disposes it until garbage
        # collection -- terminate those backends first, or DROP DATABASE
        # fails with "database is being accessed by other users".
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :dbname AND pid <> pg_backend_pid()"
        ), {"dbname": dbname})
        conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
    admin_engine.dispose()


@pytest.fixture
def keyservice_session_factory(keyservice_database_url):
    engine = make_engine(keyservice_database_url)
    KeyServiceBase.metadata.drop_all(engine)
    init_schema(engine)
    return make_session_factory(engine)
