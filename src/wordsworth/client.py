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
import time
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


def _post_json(base: str, path: str, payload: dict, timeout: float = 3600):
    """POST a JSON body and return the parsed response."""
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def _download(base: str, path: str, dest: str, params: dict | None = None,
              timeout: float = 120) -> int:
    """GET a binary payload (zip/csv) and write it to ``dest``; return byte count."""
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        data = resp.read()
    Path(dest).write_bytes(data)
    return len(data)


def _post_files(base: str, paths: list[Path], timeout: float = 600,
                domain: str | None = None):
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
        base.rstrip("/") + "/ingest"
        + ("?" + urllib.parse.urlencode({"domain": domain}) if domain else ""),
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


def _post_batch_with_retry(url, chunk, timeout, retries, index, domain: str | None = None):
    """POST one batch, retrying on transport errors / 5xx (transient: a server
    worker recycle drops the in-flight connection). Returns the parsed response,
    or None if every attempt failed. Prints each attempt's failure visibly."""
    delay = 3
    for attempt in range(1, retries + 1):
        try:
            # keyword only when set, so a domain-unaware seam/test double still fits
            return _post_files(url, chunk, timeout=timeout,
                               **({"domain": domain} if domain else {}))
        except urllib.error.HTTPError as e:
            transient = e.code >= 500
            reason = f"HTTP {e.code} {e.reason}"
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            transient = True
            reason = str(getattr(e, "reason", e))
        except ValueError as e:
            # Non-JSON / truncated response body (e.g. a proxy error page on a
            # hiccup). Treat as transient — must NOT crash the whole run.
            transient = True
            reason = f"invalid response ({e})"
        tag = f"batch @{index} (attempt {attempt}/{retries})"
        if transient and attempt < retries:
            print(f"  ! {tag}: {reason} — retrying in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
        else:
            print(f"  ! {tag}: {reason} — giving up on this batch", flush=True)
            return None
    return None


def _cmd_ingest(args) -> int:
    root = Path(args.path)
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        return 2
    files = _iter_files(root, args.all)
    if not files:
        print(f"no files to ingest under {root}", file=sys.stderr)
        return 2
    total = len(files)
    indexed = skipped = 0
    failures: list[tuple[str, str]] = []  # (filename, reason)
    print(f"ingesting {total} file(s) in batches of {args.batch}...", flush=True)
    for i in range(0, total, args.batch):
        chunk = files[i:i + args.batch]
        resp = _post_batch_with_retry(args.url, chunk, args.timeout,
                                      args.retries, i, domain=args.domain)
        if resp is None:
            # Whole batch failed after retries — the server may or may not have
            # processed some; report each file so nothing fails silently.
            for p in chunk:
                failures.append((p.name, "batch failed (see above)"))
                print(f"{p.name}: FAILED (batch @{i})", flush=True)
            continue
        for r in resp.get("results", []):
            state = r.get("state")
            if state == "indexed":
                indexed += 1
            elif state == "skipped":       # already indexed (idempotent resume)
                skipped += 1
            else:
                failures.append((r.get("filename"), r.get("error") or state))
            print(f"{r.get('filename')}: {state}{_result_extra(r)}", flush=True)
    tail = f", {skipped} skipped" if skipped else ""
    print(f"\n{indexed}/{total} indexed{tail}, {len(failures)} failed")
    if failures:
        print("failed files:")
        for name, reason in failures:
            print(f"  - {name}: {reason}")
    return 0 if not failures else 1


def _result_extra(r: dict) -> str:
    """Compact per-file suffix: duration + non-zero PII counts, or the error."""
    if r.get("duration_ms") is not None:
        parts = [f"{r['duration_ms'] / 1000:.1f}s"]
        nz = {k: v for k, v in (r.get("counts") or {}).items() if v}
        if nz:
            parts.append(" ".join(f"{k}={v}" for k, v in sorted(nz.items())))
        return f" ({', '.join(parts)})"
    if r.get("error"):
        return f" ({r['error']})"
    return ""


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


def _cmd_meta(args) -> int:
    print(json.dumps(_get(args.url, f"/documents/{args.document_id}"), indent=2))
    return 0


def _cmd_export(args) -> int:
    """Download a corpus export (de-identified ZIP) or a ranking (CSV)."""
    if args.kind == "docs":
        n = _download(args.url, "/export/anonymized.zip", args.out)
    else:  # ranking
        n = _download(args.url, "/export/ranking.csv", args.out,
                      {"query": args.query, "k": args.k})
    print(f"wrote {args.out} ({n} bytes)")
    return 0


def _cmd_reprocess(args) -> int:
    """Backfill: POST /reprocess to re-de-identify documents reversibly."""
    payload: dict = {}
    if args.ids:
        payload["document_ids"] = [x.strip() for x in args.ids.split(",") if x.strip()]
    res = _post_json(args.url, "/reprocess", payload, timeout=args.timeout or 3600)
    print(json.dumps(res, indent=2))
    return 0


def _post_dataset(base: str, path: Path, profile: str | None, profile_name: str | None,
                  timeout: float = 600) -> dict:
    """Upload a CSV + profile to POST /datasets/pseudonymize (multipart)."""
    boundary = uuid.uuid4().hex
    body = bytearray()

    def part(name: str, value: bytes, filename: str | None = None,
             ctype: str = "text/plain") -> None:
        body.extend(f"--{boundary}\r\n".encode())
        disp = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        body.extend((disp + "\r\n").encode())
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(value)
        body.extend(b"\r\n")

    part("file", path.read_bytes(), path.name, "text/csv")
    if profile is not None:
        part("profile", profile.encode())
    if profile_name is not None:
        part("profile_name", profile_name.encode())
    body.extend(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        base.rstrip("/") + "/datasets/pseudonymize", data=bytes(body), method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cmd_dataset(args) -> int:
    """Pseudonymise selected CSV columns; CSV to stdout, stats to stderr."""
    path = Path(args.csv)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2
    profile = Path(args.profile).read_text() if args.profile else None
    res = _post_dataset(args.url, path, profile, args.profile_name, args.timeout)
    sys.stdout.write(res["csv"])
    stats = {k: v for k, v in res.items() if k != "csv"}
    print(json.dumps(stats, indent=2), file=sys.stderr)
    return 0


def _cmd_grant(args) -> int:
    """Issue, inspect, or revoke a reveal grant (operator/admin surface)."""
    if args.grant_cmd == "issue":
        payload: dict = {"recipient": args.recipient}
        if args.ppl is not None:  # PPL shorthand; the server expands it
            payload["ppl"] = args.ppl
        else:
            payload["allowed_types"] = [
                t.strip() for t in (args.types or "").split(",") if t.strip()]
        if args.document:
            payload["document_id"] = args.document
        if args.domain:
            payload["domain"] = args.domain
        if args.expires:
            payload["expires_at"] = args.expires
        res = _post_json(args.url, "/grants", payload, timeout=30)
    elif args.grant_cmd == "show":
        res = _get(args.url, f"/grants/{args.grant_id}")
    else:  # revoke
        res = _post_json(args.url, f"/grants/{args.grant_id}/revoke", {}, timeout=30)
    print(json.dumps(res, indent=2))
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
    pi.add_argument("--retries", type=int, default=3,
                    help="attempts per batch on a transient error (default 3)")
    pi.add_argument("--domain", default=None,
                    help="pseudonymisation domain for this batch (default: server default)")
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

    pm = sub.add_parser("meta", help="document metadata (timing, PII counts, trail)")
    pm.add_argument("document_id")
    pm.set_defaults(func=_cmd_meta)

    pe = sub.add_parser("export", help="export the corpus (zip) or a ranking (csv)")
    esub = pe.add_subparsers(dest="kind", required=True)
    ed = esub.add_parser("docs", help="ZIP of de-identified document texts")
    ed.add_argument("out", help="output .zip path")
    ed.set_defaults(func=_cmd_export)
    er = esub.add_parser("ranking", help="CSV ranking for a query")
    er.add_argument("query")
    er.add_argument("out", help="output .csv path")
    er.add_argument("--k", type=int, default=50, help="hits to include (default 50)")
    er.set_defaults(func=_cmd_export)

    pr = sub.add_parser("reprocess",
                        help="backfill: re-de-identify documents reversibly")
    grp = pr.add_mutually_exclusive_group()
    grp.add_argument("--all", action="store_true",
                     help="reprocess all INDEXED documents (default)")
    grp.add_argument("--ids", help="comma-separated document ids to reprocess")
    pr.add_argument("--timeout", type=float, default=None,
                    help="request timeout in seconds (default 3600; long-running)")
    pr.set_defaults(func=_cmd_reprocess)

    pd = sub.add_parser("pseudonymize-dataset",
                        help="pseudonymise selected CSV columns by profile")
    pd.add_argument("csv", help="input CSV (header row required)")
    pd.add_argument("--profile", default=None, help="path to an inline profile JSON")
    pd.add_argument("--profile-name", default=None, help="server-side profiles/<name>.json")
    pd.add_argument("--timeout", type=float, default=600)
    pd.set_defaults(func=_cmd_dataset)

    pg = sub.add_parser("grant", help="issue / inspect / revoke reveal grants")
    gsub = pg.add_subparsers(dest="grant_cmd", required=True)
    gi = gsub.add_parser("issue", help="issue a reveal grant")
    gi.add_argument("--recipient", required=True)
    gi.add_argument("--types", default=None,
                    help="comma-separated PII types, e.g. PERSON,LOCATION")
    gi.add_argument("--ppl", type=int, default=None, choices=range(0, 4),
                    help="Privacy Protection Level 0-3 instead of --types "
                         "(0 none, 1 Art. 6, 2 Art. 6+9, 3 everything)")
    gi.add_argument("--document", default=None,
                    help="scope to one document id (required unless the "
                         "deployment sets WORDSWORTH_ALLOW_GLOBAL_GRANTS=true)")
    gi.add_argument("--domain", default=None,
                    help="bind to a pseudonymisation domain (default: the default domain)")
    gi.add_argument("--expires", default=None,
                    help="ISO-8601 timezone-aware expiry (e.g. 2026-12-31T00:00:00+00:00)")
    gi.set_defaults(func=_cmd_grant)
    gsh = gsub.add_parser("show", help="inspect a grant")
    gsh.add_argument("grant_id")
    gsh.set_defaults(func=_cmd_grant)
    grv = gsub.add_parser("revoke", help="revoke a grant")
    grv.add_argument("grant_id")
    grv.set_defaults(func=_cmd_grant)

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
        # Show the API's own ``detail`` when it sends one — a 400 like "document_id
        # required (global grants are not allowed)" is only actionable with it.
        detail = ""
        try:
            body = json.loads(e.read().decode("utf-8"))
            if isinstance(body, dict) and body.get("detail"):
                detail = f": {body['detail']}"
        except Exception:
            pass
        print(f"error: {args.url} returned HTTP {e.code} {e.reason}{detail}",
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
