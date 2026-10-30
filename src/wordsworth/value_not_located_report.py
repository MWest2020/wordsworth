# SPDX-License-Identifier: MIT
"""The count-by-type report over a reprocess run's `problems` (redaction-locate-
remaining).

`POST /reprocess` already names each `value-not-located` miss by document, PII
type and the located/occurrence counts (`reprocess._value_not_located_detail`,
e.g. ``"value-not-located: PERSON (0 of 1 located)"``). This module groups
those by type — a pure function over the `problems` dict, so it is testable
offline on synthetic input, and the same code an operator runs over the real
``problems`` response (design.md). It never touches a value, a page text or a
context window: only the type and the counts already in that string.
"""
from __future__ import annotations

import json
import re
import sys

_DETAIL_RE = re.compile(
    r"^value-not-located: (?P<type>\S+) \((?P<located>\d+) of "
    r"(?P<occurrences>\d+) located\)$"
)


def by_type(problems: dict[str, str]) -> dict[str, dict[str, int]]:
    """Group the `value-not-located` entries of `problems` by PII type.

    Per type: the number of documents, and the located/occurrence totals
    summed across them — nothing else. Entries that are not
    `value-not-located` (a hard failure, already reported under `failed` or
    `retryable`) are not counted here.
    """
    report: dict[str, dict[str, int]] = {}
    for detail in problems.values():
        m = _DETAIL_RE.match(detail)
        if m is None:
            continue
        bucket = report.setdefault(
            m["type"], {"documents": 0, "located": 0, "occurrences": 0})
        bucket["documents"] += 1
        bucket["located"] += int(m["located"])
        bucket["occurrences"] += int(m["occurrences"])
    return report


if __name__ == "__main__":
    # The operator step (tasks.md #3): pipe the `POST /reprocess` JSON
    # response in and get the by-type report out, e.g.
    #   wordsworth reprocess --all | python -m wordsworth.value_not_located_report
    payload = json.load(sys.stdin)
    problems = payload.get("problems", payload)
    print(json.dumps(by_type(problems), indent=2, sort_keys=True))
