# SPDX-License-Identifier: MIT
"""One grant for `mark`: PERSON and BSN on one document, issued the way
`POST /grants` issues it (store + key-lifecycle record in one transaction)."""
from __future__ import annotations

from wordsworth.grants import PostgresGrantStore, issue_grant
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit

#: The letter the reveal is rehearsed on (a parkeren letter, live, with a name).
DOCUMENT = "demo-007"
TYPES = ("PERSON", "BSN")


def seed(stand_ins, ids: dict) -> str:
    with stand_ins.session_factory() as s:
        grant = issue_grant(PostgresGrantStore(s), PostgresKeyLifecycleAudit(s),
                            "mark", list(TYPES), actor="demo-seed",
                            document_id=ids[DOCUMENT])
        s.commit()
        return grant.grant_id
