#!/usr/bin/env bash
# The wordsworth explainer film, proof-gated (docs/how-to/film.md):
#
#   tools/film/build.sh <outdir>
#
# 1. runs every check in docs/reference/film-claims.yml and writes the resolved claims;
# 2. same claims as the last build in <outdir> -> prints "unchanged", exit 0;
# 3. otherwise narrates, renders and assembles the film into <outdir> and prints the mp4.
# claims.json is written last, so a failed build is retried the next day.
set -euo pipefail

[ $# -eq 1 ] || { echo "usage: $0 <outdir>" >&2; exit 2; }
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(mkdir -p "$1" && cd "$1" && pwd)
cd "$ROOT"

NEW=$(mktemp "${TMPDIR:-/tmp}/film-claims.XXXXXX.json")
trap 'rm -f "$NEW"' EXIT
uv run -q python tools/film/claims.py "$NEW" >&2

if [ -f "$OUT/claims.json" ] && uv run -q python tools/film/claims.py --same "$NEW" "$OUT/claims.json"; then
  echo "unchanged"
  exit 0
fi

MP4=$(uv run -q --no-project --with piper-tts==1.8.0 --with playwright==1.56.0 \
        --with imageio-ffmpeg==0.7.0 python tools/film/make.py "$NEW" "$OUT" | tail -n 1)
cp "$NEW" "$OUT/claims.json"
echo "$MP4"
