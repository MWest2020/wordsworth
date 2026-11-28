"""design.md "Schema": a separate metadata means the copied shapes live in
two places and can drift. For every copied table, the service's column
names, types and nullability must equal wordsworth's model (foreign keys are
not compared -- the two databases reference different parent tables)."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, MetaData, String, Table

import wordsworth.document_keys as wordsworth_document_keys
import wordsworth.models as wordsworth_models
from wordsworth.keyservice import models as keyservice_models
from wordsworth.keyservice import models_access as keyservice_models_access

#: (wordsworth table, service table) -- every pair design.md marks "copied".
_COPIED_PAIRS = [
    (wordsworth_models.KeyVaultRecord.__table__, keyservice_models.KeyVaultRecord.__table__),
    (wordsworth_models.PiiMapping.__table__, keyservice_models.PiiMapping.__table__),
    (wordsworth_document_keys.DocumentKeyRecord.__table__,
     keyservice_models.DocumentKeyRecord.__table__),
    (wordsworth_models.GrantRecord.__table__, keyservice_models_access.GrantRecord.__table__),
    (wordsworth_models.Role.__table__, keyservice_models_access.Role.__table__),
    (wordsworth_models.GroupRole.__table__, keyservice_models_access.GroupRole.__table__),
    (wordsworth_models.KeyLifecycleEvent.__table__,
     keyservice_models_access.KeyLifecycleEvent.__table__),
]


def column_drift(reference: Table, copy: Table) -> list[str]:
    """Column names present in only one side, or present in both with a
    different type or nullability. Empty means the copy matches. Never
    compares foreign keys -- a copied table's ``document_id`` legitimately
    points at a different parent."""
    ref_cols = {c.name: c for c in reference.columns}
    copy_cols = {c.name: c for c in copy.columns}
    drift = [f"{reference.name}.{name}: missing in copy"
             for name in ref_cols.keys() - copy_cols.keys()]
    drift += [f"{reference.name}.{name}: extra in copy"
              for name in copy_cols.keys() - ref_cols.keys()]
    for name in ref_cols.keys() & copy_cols.keys():
        ref_c, copy_c = ref_cols[name], copy_cols[name]
        if (type(ref_c.type).__name__, ref_c.nullable) != (
                type(copy_c.type).__name__, copy_c.nullable):
            drift.append(
                f"{reference.name}.{name}: "
                f"{type(ref_c.type).__name__}/nullable={ref_c.nullable} vs "
                f"{type(copy_c.type).__name__}/nullable={copy_c.nullable}")
    return drift


def test_checker_catches_a_deliberately_altered_copy():
    meta = MetaData()
    reference = Table("t", meta, Column("value", String, nullable=False))
    altered = Table("t_copy", meta, Column("value", Boolean, nullable=True))
    drift = column_drift(reference, altered)
    assert len(drift) == 1
    assert "t.value" in drift[0]


def test_no_drift_in_copied_tables():
    all_drift = []
    for reference, copy in _COPIED_PAIRS:
        all_drift += column_drift(reference, copy)
    assert all_drift == []
