#!/usr/bin/env bash
# Install the Wordsworth CLI into PATH as `wordsworth` (+ `wordsworthctl`).
#
# The CLI (src/wordsworth/client.py) is stdlib-only, so this needs nothing but
# Python 3 — no package install, no dependencies. Ideal for a machine that only
# talks to the API over the tailnet (e.g. to ingest a corpus).
#
#   scripts/install-cli.sh                         # -> ~/.local/bin/wordsworth
#   scripts/install-cli.sh --url http://100.100.181.23:8000
#   scripts/install-cli.sh --bin-dir /usr/local/bin --url http://...   # (sudo)
#
# --url bakes a default API base URL into the installed copy so `wordsworth
# health` works with zero config; the WORDSWORTH_API_URL env var still overrides.
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
URL=""
SRC="$(cd "$(dirname "$0")/.." && pwd)/src/wordsworth/client.py"

while [ $# -gt 0 ]; do
  case "$1" in
    --bin-dir) BIN_DIR="$2"; shift 2 ;;
    --url)     URL="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f "$SRC" ] || { echo "cannot find client.py at $SRC" >&2; exit 1; }
mkdir -p "$BIN_DIR"
install -m 0755 "$SRC" "$BIN_DIR/wordsworth"

ln -sf "$BIN_DIR/wordsworth" "$BIN_DIR/wordsworthctl"
echo "installed: $BIN_DIR/wordsworth (+ wordsworthctl)"

if [ -n "$URL" ]; then
  # Persist the API URL to the user config so `wordsworth <cmd>` needs no --url.
  "$BIN_DIR/wordsworth" config --url "$URL" >/dev/null
  echo "default API URL: $URL  (saved to config; env/--url still override)"
else
  echo "warning: no --url given → default is http://localhost:8000." >&2
  echo "         On a remote client run e.g.:  wordsworth config --url http://100.100.181.23:8000" >&2
  echo "         (or pass --url / set WORDSWORTH_API_URL), else calls hit localhost." >&2
fi
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "note: $BIN_DIR is not on PATH — add:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
echo "try:  wordsworth health"
