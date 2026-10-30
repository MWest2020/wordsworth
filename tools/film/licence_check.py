"""The licence the film may name: the one GitHub reports AND the LICENSE file and the
source headers agree on. Prints `licence=<SPDX id>`; exits 1 when they disagree."""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
gh = subprocess.run(["gh", "api", "repos/MWest2020/wordsworth/license", "-q", ".license.spdx_id"],
                    capture_output=True, text=True, check=True).stdout.strip()
first = open(f"{ROOT}/LICENSE", encoding="utf-8").readline()
FIRST_LINE = {"MIT": "MIT LICENSE", "EUPL-1.2": "EUROPEAN UNION PUBLIC LICENCE"}
file_ok = FIRST_LINE.get(gh, "\0") in first.upper()
heads = {m.group(1) for f in glob.glob(f"{ROOT}/src/wordsworth/*.py")
         for m in [re.search(r"SPDX-License-Identifier:\s*(\S+)", open(f, encoding="utf-8").read(400))] if m}
if not file_ok or heads - {gh}:
    sys.exit(f"licence mismatch: github={gh} LICENSE={first.strip()!r} headers={sorted(heads)}")
print(f"licence={gh}")
