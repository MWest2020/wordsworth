# SPDX-License-Identifier: MIT
"""Serve the console locally on synthetic data (demo-harness).

    uv run python tools/demo/serve_local.py \\
        --database-url postgresql+psycopg://wordsworth:wordsworth@127.0.0.1/wordsworth_demo \\
        --port 8765 --reset

Creates the schema, seeds the database through the real pipeline (only when it
holds no document), and serves `create_app` in reversible mode on 127.0.0.1 with
in-process stand-ins for the index, embedder, generator, object store, transit
key and entity detector. Two callers: `mark` (reads the corpus, issues grants)
and `gast` (logged in, may do neither); their keys are new on every start and
printed below.

The stand-ins live in this process. A database seeded by an earlier run has
lost its index and its PDFs with that run, so serving it would show a dossier
whose searches find nothing and whose PDFs are missing -- without saying why.
This refuses instead: pass --reset (drops and recreates every table, only in a
database named wordsworth_demo* or wordsworth_test*) or use an empty database.
See docs/how-to/local-demo.md.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from demo import corpus  # noqa: E402
from demo.seeds import seed  # noqa: E402
from demo.wiring import StandIns, build_app  # noqa: E402

RESETTABLE = ("wordsworth_demo", "wordsworth_test")


class Refused(SystemExit):
    def __init__(self, why: str):
        super().__init__(f"serve_local: {why}")


def check_url(url: str, reset: bool) -> str:
    """The database name, after refusing what this tool must not touch."""
    u = make_url(url)
    if u.drivername != "postgresql+psycopg":
        raise Refused(f"use a postgresql+psycopg:// URL, not {u.drivername}://")
    name = u.database or ""
    if reset and not name.startswith(RESETTABLE):
        raise Refused(f"--reset drops every table; it only runs on a database "
                      f"named {' or '.join(p + '*' for p in RESETTABLE)}, "
                      f"not {name!r}")
    return name


def prepare(url: str, reset: bool):
    """Schema in place and the database empty, or refuse. Returns a session factory."""
    from wordsworth.db import init_schema, make_engine, make_session_factory
    from wordsworth.models import Base, Document

    name = check_url(url, reset)
    engine = make_engine(url)
    if reset:
        Base.metadata.drop_all(engine)
    init_schema(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        held = s.execute(select(func.count()).select_from(Document)).scalar_one()
    if held:
        raise Refused(f"{name!r} already holds {held} documents from an earlier run; "
                      "their index and PDFs died with that process. Pass --reset "
                      "or use an empty database.")
    return sf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--database-url", required=True,
                    help="postgresql+psycopg://… of a database this demo may own")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--reset", action="store_true",
                    help="drop and recreate every table first "
                         "(wordsworth_demo*/wordsworth_test* only)")
    args = ap.parse_args(argv)

    sf = prepare(args.database_url, args.reset)
    stand_ins = StandIns(sf, corpus.seeded_values(corpus.documents()))
    report = seed(stand_ins)
    keys = {secrets.token_urlsafe(18): "mark", secrets.token_urlsafe(18): "gast"}
    app = build_app(stand_ins, keys)

    base = f"http://127.0.0.1:{args.port}"
    print("\nwordsworth demo (synthetic data, stand-ins; not the real dossier)")
    print("  seeded:   " + ", ".join(f"{k} {v}" for k, v in report.items()
                                     if k not in ("grant_id", "grant_document")))
    for key, label in keys.items():
        print(f"  key {label:<5} {key}")
    print(f"  login     {base}/console/login")
    print(f"  reveal    {base}/console/documents/{report['grant_document']}"
          f"  (grant {report['grant_id'][:8]} for mark: PERSON, BSN)")
    print("  stop      Ctrl-C (the index and the PDFs go with the process)\n",
          flush=True)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
