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
This refuses instead: pass --reset (drops and recreates every table) or use an
empty database. Either way it runs only on a database named wordsworth_demo* or
wordsworth_test* (tools/demo/guard.py), and it clears every WORDSWORTH_*
variable from its own environment first, because `create_app` reads them.
See docs/how-to/local-demo.md.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo import corpus  # noqa: E402
from demo.guard import (check_database, check_url, clear_environment,  # noqa: E402
                        connected_name, refuse_if_held)
from demo.seeds import seed  # noqa: E402
from demo.wiring import StandIns, build_app  # noqa: E402


def prepare(url: str, reset: bool):
    """Schema in place and the database empty, or refuse. Returns a session factory.

    The connected name is checked before any schema work: `drop_all` and
    `init_schema` run only on a database the server itself calls a demo one."""
    from wordsworth.db import init_schema, make_engine, make_session_factory
    from wordsworth.models import Base

    check_url(url)
    engine = make_engine(url)
    name = check_database(connected_name(engine))
    if reset:
        Base.metadata.drop_all(engine)
    init_schema(engine)
    sf = make_session_factory(engine)
    refuse_if_held(sf, name)
    return sf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--database-url", required=True,
                    help="postgresql+psycopg://…/wordsworth_demo* or …/wordsworth_test*")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--reset", action="store_true",
                    help="drop and recreate every table first")
    args = ap.parse_args(argv)

    cleared = clear_environment()
    sf = prepare(args.database_url, args.reset)
    stand_ins = StandIns(sf, corpus.seeded_values(corpus.documents()))
    report = seed(stand_ins)
    keys = {secrets.token_urlsafe(18): "mark", secrets.token_urlsafe(18): "gast"}
    app = build_app(stand_ins, keys)

    base = f"http://127.0.0.1:{args.port}"
    print("\nwordsworth demo (synthetic data, stand-ins; not the real dossier)")
    if cleared:
        print("  ignored:  " + ", ".join(cleared) + " (cleared from this process)")
    print("  seeded:   " + ", ".join(f"{k} {v}" for k, v in report.items()
                                     if k not in ("seeded", "grant_id", "grant_document")))
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
