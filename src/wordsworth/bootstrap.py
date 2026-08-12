"""One-shot schema bootstrap: create tables + the append-only audit trigger.

Idempotent (``CREATE OR REPLACE`` / ``DROP ... IF EXISTS`` inside
``init_schema``). Run once before serving or ingesting (``wordsworth-init``).
Requires a DB role permitted to create functions and triggers.
"""
from __future__ import annotations

from .db import init_schema, make_engine


def main() -> int:
    init_schema(make_engine())
    print("schema ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
