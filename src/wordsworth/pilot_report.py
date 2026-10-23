"""The pilot's completed pre-fetch check -- robots.txt, terms, and the Anubis
proof-of-work status -- gates a manifest run before the manifest itself is
read (pilot-ingest-manifest). "A template that can be filled in afterwards
proves nothing" (the reviewer, on the pilot plan): this only checks that the
fields are present and the decision is `proceed`, never that they are true --
git commit order (report before manifest) is what actually proves that, and
is not this script's job to verify.

The report's path and exact authoring convention are `pilot-report-template`'s
to define; this module only validates whatever file `--pilot-report` names.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FIELDS = ("who", "when", "robots_txt", "terms", "anubis_status", "decision")


class PilotReportError(ValueError):
    """The pilot report has no completed check, or its decision is not
    `proceed`. The run that raises this refuses before any file is ingested."""


def require_completed_check(path: Path) -> None:
    if not path.is_file():
        raise PilotReportError(f"pilot report not found: {path}")
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PilotReportError(f"pilot report is not valid JSON: {path}") from exc
    missing = [field for field in REQUIRED_FIELDS if not report.get(field)]
    if missing:
        raise PilotReportError(
            "pilot report has no completed check, missing: " + ", ".join(missing))
    if report["decision"] != "proceed":
        raise PilotReportError(
            f"pilot report decision is {report['decision']!r}, not 'proceed'")
