#!/usr/bin/env python3
"""``wordsworth`` / ``wordsworthctl`` — a tiny client for the Wordsworth HTTP API.

Stdlib only (no dependencies), so it runs anywhere with Python 3.12 — copy this
one file to a machine on the tailnet and run it, or use the installed
``wordsworthctl`` entrypoint.

    wordsworthctl --url http://100.100.181.23:8000 health
    wordsworthctl --url http://100.100.181.23:8000 ingest /path/to/corpus
    wordsworthctl --url http://100.100.181.23:8000 search "vergunning"
    wordsworthctl --url http://100.100.181.23:8000 state <document-id>

``ingest`` takes a file or a directory (walked recursively; ``*.pdf`` by default,
``--all`` for every file) and uploads to ``POST /ingest`` in batches, printing a
per-file result and a final summary. The base URL defaults to
``$WORDSWORTH_API_URL`` or ``http://localhost:8000``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

DEFAULT_URL = "http://localhost:8000"
CONFIG_PATH = Path(os.environ.get(
    "WORDSWORTH_CONFIG",
    str(Path.home() / ".config" / "wordsworth" / "config.yaml")))


def _load_config() -> dict[str, str]:
    """Read a flat ``key: value`` config (a small YAML subset: url, batch,
    timeout). Missing/unreadable file → empty. Stdlib only (no YAML dep)."""
    cfg: dict[str, str] = {}
    try:
        text = CONFIG_PATH.read_text()
    except OSError:
        return cfg
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        cfg[key.strip()] = val.strip().strip('"').strip("'")
    return cfg


def _resolve_url(flag: str | None, cfg: dict[str, str]) -> str:
    # --url flag > $WORDSWORTH_API_URL > config file > built-in default.
    return (flag or os.environ.get("WORDSWORTH_API_URL")
            or cfg.get("url") or DEFAULT_URL)


def _get(base: str, path: str, params: dict | None = None, timeout: float = 30):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def _post_files(base: str, paths: list[Path], timeout: float = 600):
    """Upload files to POST /ingest as multipart/form-data (field name ``files``)."""
    boundary = uuid.uuid4().hex
    body = bytearray()
    for p in paths:
        body += f'--{boundary}\r\n'.encode()
        body += (
            f'Content-Disposition: form-data; name="files"; '
            f'filename="{p.name}"\r\n'
        ).encode()
        body += b"Content-Type: application/pdf\r\n\r\n"
        body += p.read_bytes()
        body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/ingest",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def _iter_files(root: Path, include_all: bool) -> list[Path]:
    if root.is_file():
        return [root]
    pattern = "*" if include_all else "*.pdf"
    return sorted(p for p in root.rglob(pattern) if p.is_file())


def _cmd_ingest(args) -> int:
    root = Path(args.path)
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        return 2
    files = _iter_files(root, args.all)
    if not files:
        print(f"no files to ingest under {root}", file=sys.stderr)
        return 2
    total = indexed = failed = 0
    for i in range(0, len(files), args.batch):
        chunk = files[i:i + args.batch]
        try:
            resp = _post_files(args.url, chunk, timeout=args.timeout)
        except urllib.error.HTTPError as e:
            print(f"batch {i}-{i+len(chunk)}: HTTP {e.code} {e.reason}",
                  file=sys.stderr)
            failed += len(chunk)
            continue
        for r in resp.get("results", []):
            total += 1
            if r.get("state") == "indexed":
                indexed += 1
            else:
                failed += 1
            print(f"{r.get('filename')}: {r.get('state')}"
                  + (f" ({r['error']})" if r.get("error") else ""))
    print(f"\n{indexed}/{total} indexed, {failed} failed")
    return 0 if failed == 0 else 1


def _cmd_health(args) -> int:
    print(json.dumps(_get(args.url, "/health")))
    return 0


def _cmd_search(args) -> int:
    print(json.dumps(_get(args.url, "/search",
                          {"q": args.query, "size": args.size}), indent=2))
    return 0


def _cmd_hybrid(args) -> int:
    print(json.dumps(_get(args.url, "/hybrid",
                          {"q": args.query, "size": args.size}), indent=2))
    return 0


def _cmd_ask(args) -> int:
    # RAG answer: local LLM over CPU can be slow → generous timeout.
    print(json.dumps(_get(args.url, "/ask", {"q": args.query, "k": args.k},
                          timeout=610), indent=2))
    return 0


def _cmd_state(args) -> int:
    print(json.dumps(_get(args.url, f"/documents/{args.document_id}/state")))
    return 0


def _cmd_config(args) -> int:
    """Show or set persistent CLI defaults in the config file."""
    cfg = _load_config()
    updates = {k: getattr(args, k) for k in ("url", "batch", "timeout")
               if getattr(args, k) is not None}
    if not updates or args.show:
        print(f"config: {CONFIG_PATH}")
        for k in ("url", "batch", "timeout"):
            if k in cfg:
                print(f"{k}: {cfg[k]}")
        return 0
    cfg.update({k: str(v) for k, v in updates.items()})
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text("".join(f"{k}: {v}\n" for k, v in cfg.items()))
    print(f"wrote {CONFIG_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Client for the Wordsworth HTTP API.")
    parser.add_argument("--url", default=None,
                        help="API base URL "
                             "(--url > $WORDSWORTH_API_URL > config file > "
                             f"{DEFAULT_URL})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health", help="check the API is up").set_defaults(
        func=_cmd_health)

    pi = sub.add_parser("ingest", help="upload a file or directory to /ingest")
    pi.add_argument("path", help="a PDF file or a directory of PDFs")
    pi.add_argument("--all", action="store_true",
                    help="upload every file, not just *.pdf")
    pi.add_argument("--batch", type=int, default=None,
                    help="files per request (config 'batch', else 25)")
    pi.add_argument("--timeout", type=float, default=None,
                    help="per-batch timeout in seconds (config 'timeout', else 600)")
    pi.set_defaults(func=_cmd_ingest)

    ps = sub.add_parser("search", help="lexical (BM25) search")
    ps.add_argument("query")
    ps.add_argument("--size", type=int, default=10)
    ps.set_defaults(func=_cmd_search)

    ph = sub.add_parser("hybrid", help="hybrid (BM25 + vector) relevance search")
    ph.add_argument("query")
    ph.add_argument("--size", type=int, default=10)
    ph.set_defaults(func=_cmd_hybrid)

    pa = sub.add_parser("ask", help="RAG question answering (local LLM)")
    pa.add_argument("query")
    pa.add_argument("--k", type=int, default=5, help="passages to retrieve")
    pa.set_defaults(func=_cmd_ask)

    pst = sub.add_parser("state", help="pipeline state of a document")
    pst.add_argument("document_id")
    pst.set_defaults(func=_cmd_state)

    pc = sub.add_parser("config", help="show or set CLI defaults (url/batch/timeout)")
    pc.add_argument("--url")
    pc.add_argument("--batch", type=int)
    pc.add_argument("--timeout", type=float)
    pc.add_argument("--show", action="store_true", help="print config and exit")
    pc.set_defaults(func=_cmd_config)

    args = parser.parse_args(argv)

    # Resolve defaults from the config file (flag > env > config > built-in).
    cfg = _load_config()
    if args.cmd == "config":
        return args.func(args)  # local file op; skip network error handling

    args.url = _resolve_url(args.url, cfg)
    if args.cmd == "ingest":
        if args.batch is None:
            args.batch = int(cfg.get("batch", 25))
        if args.timeout is None:
            args.timeout = float(cfg.get("timeout", 600))

    try:
        return args.func(args)
    except urllib.error.HTTPError as e:
        print(f"error: {args.url} returned HTTP {e.code} {e.reason}",
              file=sys.stderr)
        return 1
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        reason = getattr(e, "reason", e)
        print(f"error: cannot reach Wordsworth API at {args.url}: {reason}\n"
              f"       set --url or $WORDSWORTH_API_URL to the API "
              f"(e.g. http://100.100.181.23:8000)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
