# SPDX-License-Identifier: MIT
"""`wordsworth-sealed-orphans`: list (and, with `--apply`, remove) sealed
objects under `documents/` that open under no key row -- there is no row for
their key, or the row names another key id.

S3 and Postgres cannot share one transaction (design.md "Orphans"): a sealed
object written while the database transaction then rolled back ends up in
exactly this state. It is unreadable by construction (no plaintext risk);
the next write of the same bytes repairs it; this sweep removes what nothing
repairs.

- **Dry run by default.** It prints what it would do and changes nothing.
- **Older than one hour only**, so a write in flight is never touched.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from . import originals_envelope
from .document_keys import DocumentKeyRecord
from .object_store import ObjectStore, ObjectStoreError

PREFIX = "documents/"
MIN_AGE = timedelta(hours=1)


def _is_sealed(data: bytes) -> bool:
    return data[:len(originals_envelope.HEADER_MAGIC)] == originals_envelope.HEADER_MAGIC


def find_orphans(session, objects: ObjectStore, *,
                 now: datetime | None = None) -> list[tuple[str, datetime]]:
    """[(key, last_modified)] for every sealed object under `documents/` that
    opens under no key row and is older than one hour."""
    now = now or datetime.now(timezone.utc)
    orphans = []
    for key, last_modified in objects.iter_objects(PREFIX):
        if now - last_modified < MIN_AGE:
            continue  # a write in flight -- never touched
        try:
            data = objects.get_raw(key)
        except ObjectStoreError:
            continue  # removed between listing and inspection
        if not _is_sealed(data):
            continue  # legacy plaintext, never our business
        try:
            header_key_id = originals_envelope.header_key_id(data)
        except ValueError:
            continue  # malformed header -- not a wordsworth sealed object
        row = session.get(DocumentKeyRecord, key)
        if row is not None and row.key_id == header_key_id:
            continue  # sealed under its own row
        orphans.append((key, last_modified))
    return orphans


def run(session_factory, objects: ObjectStore, *, apply: bool,
       now: datetime | None = None) -> dict:
    with session_factory() as session:
        orphans = find_orphans(session, objects, now=now)
    report: dict = {"found": [key for key, _ in orphans], "applied": False}
    if not apply:
        return report
    removed = [key for key in report["found"] if objects.delete(key)]
    report.update(applied=True, removed=removed)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wordsworth-sealed-orphans",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="actually remove the orphans")
    args = ap.parse_args(argv)

    from .db import make_engine, make_session_factory
    from .object_store import S3ObjectStore
    report = run(make_session_factory(make_engine()), S3ObjectStore.from_config(),
                apply=args.apply)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
