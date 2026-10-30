"""Numbers from the published pilot report (docs/explanation/pilot-report-gooise-meren-2022.md):
the ranking table (rank per question) and the PII-read outcome line. Prints key=value."""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
text = open(f"{ROOT}/docs/explanation/pilot-report-gooise-meren-2022.md", encoding="utf-8").read()
table = re.search(r"\| # \| expected document found in top 8\? \| rank \|\n\|[-| ]+\|\n((?:\|.*\|\n)+)", text)
outcome = re.search(r"\*\*Outcome:\*\* (\d+) of (\d+) documents pass", text)
if not table or not outcome:
    sys.exit("pilot report: ranking table or outcome line not found")
ranks = [int(r.split("|")[3]) for r in table.group(1).strip().splitlines()]
print(f"q_total={len(ranks)}")
print(f"q_top2={sum(1 for r in ranks if r <= 2)}")
print(f"sample_clean={outcome.group(1)}")
print(f"sample_n={outcome.group(2)}")
