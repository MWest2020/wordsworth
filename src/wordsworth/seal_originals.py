# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` (ADR-0008, originals-encrypt-existing): seal the
existing plaintext corpus, verifiably, without losing a document -- every live
document's original, the original scan of a live document recovered by OCR,
and a scan OCR recovery retired as a copy (#486). The per-object mechanics (verify-before-replace, resumability) live in
`originals_seal.py`; this module is the report and the CLI.

A run without flags seals for real; ``--dry-run`` reports what would be
sealed and changes nothing. Classifying an object (the counts, the dry run,
``--verify``) reads its size and its sealed header, never the whole object:
only a real seal reads an object in full, and a rerun reads only the header
of one that is sealed and committed (#491). An object that cannot be read is
reported ``unreadable``, never ``missing``. ``--verify`` (`seal_verify.py`)
checks the outcome of a real run (or a deploy before one): it fails while any
live document or scan is still a legacy plaintext original, or a sealed object
has no usable key row.

Every object is its own attempt: an exception sealing one (the key service
unavailable, a store error) is reported as ``failed`` with the exception's
class name only -- never its message, which could carry content -- and the
run goes on with the next.
"""
from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from .object_store import ObjectStore
from .originals_seal import seal_one
from .seal_candidates import candidates, classify, counts
from .seal_verify import verify


def run(session_factory, store: ObjectStore, keys, *,
       dry_run: bool, ids: list[UUID] | None = None) -> dict:
    with session_factory() as session:
        work = candidates(session, ids)
    states = classify(store, work)  # HEAD + header reads only, never a full GET
    before = counts(store, work, states)

    if dry_run:
        def keys_in(state: str) -> list[str]:
            return [c.object_key for c in work if states[c.object_key][0] == state]
        return {"dry_run": True, "before": before, "would_seal": keys_in("legacy"),
                "unreadable": keys_in("unreadable")}

    results = []
    done = {"sealed": 0, "scans": 0, "already_sealed": 0, "gone": 0,
            "skipped_deleted": 0, "skipped_moved": 0, "failed": 0}
    for c in work:
        try:
            with session_factory() as session:
                outcome = seal_one(session, store, keys, c.document_id, c.object_key, c.kind)
        except Exception as exc:  # one object's failure never ends the run
            outcome = {"status": "failed", "error": type(exc).__name__}
        status = outcome["status"]
        results.append({"document_id": str(c.document_id), "object_key": c.object_key,
                        "kind": c.kind, **outcome})
        if status == "sealed":
            done["scans" if c.kind == "scan" else "sealed"] += 1
        elif status in ("already_sealed", "gone", "skipped_deleted", "skipped_moved"):
            # `gone`: a scan no longer in the store (removed with an old copy,
            # by sealed-orphans, ...) -- nothing to seal, nothing failed (spec).
            done[status] += 1
        else:
            done["failed"] += 1

    with session_factory() as session:
        after_work = candidates(session, ids)
    after = counts(store, after_work)
    return {"dry_run": False, "before": before, "after": after, "done": done,
           "failed": done["failed"], "results": results}


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
                        "is still a legacy plaintext original, or a sealed "
                        "object has no key row or a mismatched key id")
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
