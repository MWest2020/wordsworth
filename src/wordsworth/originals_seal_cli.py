# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals`: the report, `--dry-run`/`--verify` and the CLI
entry point for `originals_seal.py`'s engine (`candidates`, `seal_one`).

``--dry-run`` (the default mode) lists what would be sealed and changes
nothing. Without it, every candidate is sealed one at a time (`seal_one`),
and the before/after report counts objects, sealed/legacy and bytes --
separately for originals and for scans -- never a document's name, text or
any value. ``--verify`` instead checks that no live document (or live
recovered document's scan) still has a legacy plaintext original, and
changes nothing either."""
from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from sqlalchemy.orm import Session

from .document_keys import DocumentKeys
from .object_store import ObjectStore, ObjectStoreError
from .originals_seal import Candidate, candidates, is_sealed, seal_one


def _bucket_summary(store: ObjectStore, work: list[Candidate]) -> dict:
    buckets = {"originals": {"objects": 0, "sealed": 0, "legacy": 0, "bytes": 0},
               "scans": {"objects": 0, "sealed": 0, "legacy": 0, "bytes": 0}}
    key_for = {"original": "originals", "scan": "scans"}
    for c in work:
        try:
            data = store.get_raw(c.object_key)
        except ObjectStoreError:
            continue
        bucket = buckets[key_for[c.kind]]
        bucket["objects"] += 1
        bucket["bytes"] += len(data)
        if is_sealed(data):
            bucket["sealed"] += 1
        else:
            bucket["legacy"] += 1
    return buckets


def run(session_factory, store: ObjectStore, keys: DocumentKeys, *,
        dry_run: bool, ids: set[UUID] | None = None) -> dict:
    with session_factory() as session:
        work, gone = candidates(session, store, ids=ids)
        before = _bucket_summary(store, work)

    if dry_run:
        return {
            "before": before,
            "after": before,
            "would_seal": [c.as_dict() for c in work],
            "gone": [g.as_dict() for g in gone],
            "applied": False,
        }

    results = []
    sealed = scans = failed = 0
    gone_count = len(gone)
    for c in work:
        outcome = seal_one(session_factory, store, keys, c.document_id, c.object_key)
        results.append({**c.as_dict(), **outcome})
        if outcome["status"] == "sealed":
            sealed += 1
            if c.kind == "scan":
                scans += 1
        elif outcome["status"] == "failed":
            failed += 1
        elif outcome["status"] == "gone":
            gone_count += 1

    results.extend({**g.as_dict(), "status": "gone"} for g in gone)
    after = _bucket_summary(store, work)

    return {
        "before": before, "after": after,
        "sealed": sealed, "scans": scans, "failed": failed, "gone": gone_count,
        "results": results, "applied": True,
    }


def verify(session: Session, store: ObjectStore) -> dict:
    """``{"ok": ..., "legacy": [...], "gone": [...]}`` -- whether any live
    document (or live recovered document's scan) still has a legacy
    plaintext original. Reads only; changes nothing."""
    work, gone = candidates(session, store)
    legacy = [c.as_dict() for c in work if not is_sealed(store.get_raw(c.object_key))]
    return {"ok": not legacy, "legacy": legacy, "gone": [g.as_dict() for g in gone]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wordsworth-seal-originals",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be sealed; change nothing")
    ap.add_argument("--ids", nargs="*", help="only seal these document ids")
    ap.add_argument("--verify", action="store_true",
                    help="check that no live document has a legacy plaintext "
                         "original (or scan); changes nothing")
    args = ap.parse_args(argv)

    from .config import settings
    from .db import make_engine, make_session_factory
    from .object_store import S3ObjectStore
    from .transit import transit_factory

    session_factory = make_session_factory(make_engine())
    store = S3ObjectStore.from_config()
    ids = {UUID(i) for i in args.ids} if args.ids else None

    if args.verify:
        with session_factory() as session:
            report = verify(session, store)
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["ok"] else 1

    keys = DocumentKeys(transit_factory(settings.openbao_url, settings.openbao_token))
    report = run(session_factory, store, keys, dry_run=args.dry_run, ids=ids)
    print(json.dumps(report, indent=2, default=str))
    return 1 if report.get("failed", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
