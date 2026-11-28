"""design.md "Tests": the service's private test database is a different
database from wordsworth's, so dropping and creating
``KeyServiceBase.metadata`` there never touches wordsworth's test tables."""
from __future__ import annotations

from sqlalchemy import inspect

import wordsworth.models as wordsworth_models


def test_keyservice_db_is_not_wordsworth_db(keyservice_database_url, database_url):
    assert keyservice_database_url != database_url


def test_keyservice_schema_leaves_wordsworth_tables_untouched(
        session_factory, keyservice_session_factory, database_url):
    # `session_factory` created wordsworth's tables in `database_url`;
    # `keyservice_session_factory` just dropped+created KeyServiceBase.metadata
    # in a SEPARATE database. wordsworth's tables must still all be there.
    from wordsworth.keyservice.db import make_engine as make_keyservice_engine

    wordsworth_engine = make_keyservice_engine(database_url)
    tables = set(inspect(wordsworth_engine).get_table_names())
    assert set(wordsworth_models.Base.metadata.tables) <= tables
