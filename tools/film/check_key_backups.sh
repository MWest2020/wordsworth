#!/usr/bin/env bash
# Film claim `key-backups`: both nightly key backups (homelab #40) succeeded in the
# last 36 hours. Reads only the CronJobs' status; no backup content.
set -euo pipefail
ssh -o BatchMode=yes jumpy '
  kubectl -n wordsworth get cronjob wordsworth-keys-backup -o jsonpath="{.status.lastSuccessfulTime}{\"\n\"}"
  kubectl -n openbao get cronjob openbao-snapshot -o jsonpath="{.status.lastSuccessfulTime}{\"\n\"}"' |
python3 -c '
import sys, datetime as d
ts = [l.strip() for l in sys.stdin if l.strip()]
now = d.datetime.now(d.timezone.utc)
age = [(now - d.datetime.fromisoformat(t.replace("Z", "+00:00"))).total_seconds() / 3600 for t in ts]
sys.exit(0 if len(age) == 2 and max(age) < 36 else 1)'
