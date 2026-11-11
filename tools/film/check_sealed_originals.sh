#!/usr/bin/env bash
# Film claim `sealed-originals`: new originals are sealed at rest (ADR-0008,
# originals-ingest-switch, verified 2026-11-10 in #379). Passes only when, in
# production, document_keys has a row, the newest sealed original in SeaweedFS
# starts with the WWENC header, and /health answers 200. Read-only: it fetches
# 5 bytes of one object and prints only counts and the header verdict, never a
# key, an object name or document content. Any error fails closed.
set -euo pipefail
ssh -o BatchMode=yes jumpy 'kubectl -n wordsworth exec -i deploy/wordsworth-api -- /app/.venv/bin/python -' <<'PY'
import sys, urllib.request
from sqlalchemy import text
from wordsworth.config import settings
from wordsworth.db import make_engine
from wordsworth.object_store import S3ObjectStore
with make_engine().connect() as c:
    rows = c.execute(text("select count(*) from document_keys")).scalar()
    key = c.execute(text("select object_key from document_keys order by sealed_at desc nulls last limit 1")).scalar()
head = b""
if key:
    store = S3ObjectStore.from_config()
    head = store._client.get_object(Bucket=settings.s3_bucket, Key=key, Range="bytes=0-4")["Body"].read()
health = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=10).status
sealed = head == b"WWENC"
print(f"rows={rows} sealed_header={'yes' if sealed else 'no'} health={health}")
sys.exit(0 if rows > 0 and sealed and health == 200 else 1)
PY
