# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` (ADR-0008, originals-encrypt-existing): seal the
existing plaintext corpus, verifiably, without losing a document -- every live
document's original, and the original scan of a live document recovered by
OCR. The per-object mechanics (verify-before-replace, resumability) live in
`originals_seal.py`; this module is the report and the CLI.

Dry run is the default shape every CLI here uses: report, change nothing.
``--verify`` checks the outcome of a real run (or a deploy before one):
whether any live document or scan is still a legacy plaintext original.
"""
from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from .object_store import ObjectStore
from .originals_seal import candidates, counts, object_state, seal_one


def run(session_factory, store: ObjectStore, keys, *,
       dry_run: bool, ids: list[UUID] | None = None) -> dict:
    with session_factory() as session:
        work = candidates(session, ids)
    before = counts(store, work)

    if dry_run:
        would_seal = [c.object_key for c in work if object_state(store, c.object_key)[0] == "legacy"]
        return {"dry_run": True, "before": before, "would_seal": would_seal}

    results = []
    done = {"sealed": 0, "scans": 0, "already_sealed": 0, "scan_gone": 0, "failed": 0}
    for c in work:
        if c.kind == "scan" and object_state(store, c.object_key)[0] == "missing":
            # A scan no longer in the store (removed with an old copy, by
            # sealed-orphans, ...) is nothing to seal and nothing failed (spec:
            # "A scan that is already sealed or gone is left alone").
            done["scan_gone"] += 1
            continue
        with session_factory() as session:
            outcome = seal_one(session, store, keys, c.document_id, c.object_key)
        results.append({"document_id": str(c.document_id), "object_key": c.object_key,
                        "kind": c.kind, **outcome})
        if outcome["status"] == "sealed":
            done["scans" if c.kind == "scan" else "sealed"] += 1
        elif outcome["status"] == "already_sealed":
            done["already_sealed"] += 1
        else:
            done["failed"] += 1

    with session_factory() as session:
        after_work = candidates(session, ids)
    after = counts(store, after_work)
    return {"dry_run": False, "before": before, "after": after, "done": done,
           "failed": done["failed"], "results": results}


def verify(session, store: ObjectStore, ids: list[UUID] | None = None) -> dict:
    """``{"verified": True}`` iff no live document or scan is still a legacy
    plaintext original; else the offending object keys, never content."""
    legacy = [{"document_id": str(c.document_id), "object_key": c.object_key, "kind": c.kind}
             for c in candidates(session, ids)
             if object_state(store, c.object_key)[0] == "legacy"]
    return {"verified": not legacy, "legacy": legacy}


def main(argv: list[str] | None = None, *, session_factory=None, store=None, keys=None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-seal-originals",
        description="Seal the existing plaintext corpus: every live document's "
                    "original, and the original scan of a live document "
                    "recovered by OCR, each verified before its plaintext is "
                    "replaced.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be sealed; change nothing")
    ap.add_argument("--verify", action="store_true",
                    help="check only: fails if a live document or its scan "
                        "is still a legacy plaintext original")
    ap.add_argument("--ids", nargs="+", help="limit to these document id(s) (uuid)")
    args = ap.parse_args(argv)
    if args.dry_run and args.verify:
        ap.error("--dry-run and --verify are mutually exclusive")

    try:
        ids = [UUID(i) for i in args.ids] if args.ids else None
    except ValueError as exc:
        ap.error(f"not a uuid: {exc}")

    if session_factory is None:
        from .db import make_engine, make_session_factory

        session_factory = make_session_factory(make_engine())
    if store is None:
        from .object_store import S3ObjectStore

        store = S3ObjectStore.from_config()

    if args.verify:
        with session_factory() as session:
            report = verify(session, store, ids)
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["verified"] else 1

    if keys is None:
        from .originals_io import originals_from_config

        keys = originals_from_config(store).keys

    report = run(session_factory, store, keys, dry_run=args.dry_run, ids=ids)
    print(json.dumps(report, indent=2, default=str))
    return 1 if report.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
