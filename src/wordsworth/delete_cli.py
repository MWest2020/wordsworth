# SPDX-License-Identifier: MIT
"""`wordsworth-delete`: remove one or more documents' content, or a dossier.

``--dry-run`` reports the counts it would remove, using the exact same code
path as a real run (`deletion.delete_document`), and stops before the first
removal: nothing changes, and no `deleted` record is written. Without it, each
named document is deleted and committed on its own -- the same shape as
`wordsworth-dedupe` -- so a failure partway through a multi-document run
leaves only the untouched documents for a rerun to finish.

``--dossier`` deletes a dossier instead (the CLI counterpart of
`DELETE /dossiers/{id}`, `dossier_deletion.delete_dossier`): its memberships
and the dossier row go, and a member document is deleted only if it belongs to
no other dossier. ``--dry-run`` reports which documents would be deleted and
which only released, through that same code path.

Only role `beheerder` or a configured issuer label may run either without
``--dry-run``; ``--actor`` names who is asking, checked the same way the API
checks a caller (`auth.authorize_delete`). A refusal removes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from . import roles
from .auth import authorize_delete
from .deletion import DeletionError, delete_document
from .dossier_deletion import DossierDeletionError, delete_dossier
from .grants import caller_holds_role


def run(session_factory, store, index, document_ids: list[UUID], *,
        dry_run: bool, actor: str) -> dict:
    results = []
    for document_id in document_ids:
        with session_factory() as session:
            try:
                counts = delete_document(session, document_id, store, index,
                                         actor=actor, dry_run=dry_run)
            except DeletionError as exc:
                results.append({"document_id": str(document_id), "error": str(exc)})
                continue
            if not dry_run:
                session.commit()
            results.append({"document_id": str(document_id), **counts.as_dict()})
    return {"dry_run": dry_run, "results": results}


def run_dossier(session_factory, store, index, dossier_id: UUID, *,
                dry_run: bool, actor: str) -> dict:
    with session_factory() as session:
        try:
            report = delete_dossier(session, dossier_id, store, index,
                                    actor=actor, dry_run=dry_run)
        except DossierDeletionError as exc:
            return {"dry_run": dry_run,
                   "results": [{"dossier_id": str(dossier_id), "error": str(exc)}]}
        if not dry_run:
            session.commit()
        return {"dry_run": dry_run,
               "results": [{"dossier_id": str(dossier_id), **report.as_dict()}]}


def main(argv: list[str] | None = None, *, session_factory=None, store=None,
        index=None, issuer_labels: list[str] | None = None) -> int:
    """Entry point. ``session_factory``/``store``/``index``/``issuer_labels``
    are overridable so a test can drive this exact function against fakes
    instead of the real database/S3/OpenSearch/settings -- the production
    console script calls it with none of them and gets the real backends."""
    ap = argparse.ArgumentParser(
        prog="wordsworth-delete",
        description="Remove a document's content: the stored object, its "
                    "text, its pseudonyms, its mappings, its index entry and "
                    "its grants. The documents row and its audit trail stay. "
                    "With --dossier, remove a dossier instead: its "
                    "memberships and the dossier row, deleting each member "
                    "that belongs to no other dossier.")
    ap.add_argument("document", nargs="*", help="document id(s) (uuid)")
    ap.add_argument("--dossier", help="dossier id (uuid) -- delete the "
                    "dossier instead of named documents")
    ap.add_argument("--dry-run", action="store_true",
                    help="report the counts; remove nothing")
    ap.add_argument("--actor", required=True,
                    help="who is asking -- checked against role beheerder "
                         "or WORDSWORTH_GRANT_ISSUER_LABELS")
    args = ap.parse_args(argv)

    if bool(args.document) == bool(args.dossier):
        ap.error("give document id(s), or --dossier <id>, not both and not neither")

    try:
        document_ids = [UUID(d) for d in args.document]
        dossier_id = UUID(args.dossier) if args.dossier else None
    except ValueError as exc:
        ap.error(f"not a uuid: {exc}")

    if session_factory is None:
        from .db import make_engine, make_session_factory

        session_factory = make_session_factory(make_engine())
    if issuer_labels is None:
        from .config import settings

        issuer_labels = settings.grant_issuer_labels
    with session_factory() as session:
        beheerder = caller_holds_role(session, args.actor, roles.ADMIN)
    if not authorize_delete(args.actor, issuer_labels, auth_enabled=True,
                            is_beheerder=beheerder):
        print(f"{args.actor!r} may not delete: not the beheerder role, "
              "not an issuer label", file=sys.stderr)
        return 1

    if store is None:
        from .object_store import S3ObjectStore

        store = S3ObjectStore.from_config()
    if index is None:
        from .opensearch_index import OpenSearchIndex

        index = OpenSearchIndex.from_config()

    if dossier_id is not None:
        report = run_dossier(session_factory, store, index, dossier_id,
                             dry_run=args.dry_run, actor=args.actor)
    else:
        report = run(session_factory, store, index, document_ids,
                    dry_run=args.dry_run, actor=args.actor)
    print(json.dumps(report, indent=2, default=str))
    return 1 if any("error" in r for r in report["results"]) else 0


if __name__ == "__main__":
    sys.exit(main())
