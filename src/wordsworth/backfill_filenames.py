# SPDX-License-Identifier: MIT
"""Give existing documents back the name their file arrived under.

Ingestion has always been content-addressed: ``documents/<sha256>``. That is the
right identity and it is also unreadable, and until now the name the file came in
under was returned to the caller and then dropped.

For documents ingested before the column existed the name is not in the database
at all. It IS still on disk wherever the corpus lives, and the hash is the bridge:
hash a file, and if that key names a document, that document had that filename.

What this does NOT do is guess. A document whose bytes are not in the directory
keeps no name, and the console then says "naamloos" rather than printing a hash
where a name belongs.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from sqlalchemy import select

from .db import make_engine, make_session_factory
from .models import Document


def keys_in(directory: Path) -> dict[str, str]:
    """``object_key -> filename`` for every file in the directory.

    Same bytes under two names is one key; the first name in sorted order wins,
    so a re-run gives the same answer. Arbitrary, and deterministic beats
    whichever one the filesystem happened to hand over first.
    """
    out: dict[str, str] = {}
    for path in sorted(p for p in directory.iterdir() if p.is_file()):
        key = "documents/" + hashlib.sha256(path.read_bytes()).hexdigest()
        out.setdefault(key, path.name)
    return out


def backfill(session, names: dict[str, str], overwrite: bool = False) -> dict:
    """Link names to documents by content hash. Returns what happened.

    An existing name is kept unless ``overwrite``: a name already recorded came
    from the caller at ingest time, which is a better source than a file that
    happens to sit in a directory today.
    """
    stats = {"matched": 0, "named": 0, "kept": 0, "unmatched_documents": 0}
    for doc in session.execute(select(Document)).scalars():
        name = names.get(doc.object_key)
        if name is None:
            stats["unmatched_documents"] += 1
            continue
        stats["matched"] += 1
        if doc.filename and not overwrite:
            stats["kept"] += 1
            continue
        doc.filename = name
        stats["named"] += 1
    stats["files_without_document"] = sum(
        1 for key in names
        if session.execute(select(Document.id).where(
            Document.object_key == key)).first() is None)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-backfill-filenames",
        description="Link document names by content hash from a corpus directory")
    ap.add_argument("directory", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace a name that is already recorded")
    args = ap.parse_args(argv)

    names = keys_in(args.directory)
    with make_session_factory(make_engine())() as session:
        stats = backfill(session, names, args.overwrite)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    print(f"{'zou benoemen' if args.dry_run else 'benoemd'}: {stats['named']} "
          f"document(en) uit {len(names)} bestand(en)")
    print(f"  behield een naam        : {stats['kept']}")
    print(f"  document zonder bestand : {stats['unmatched_documents']}")
    print(f"  bestand zonder document : {stats['files_without_document']}")
    return 0


if __name__ == "__main__":     # pragma: no cover
    raise SystemExit(main())
