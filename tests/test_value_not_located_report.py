# SPDX-License-Identifier: MIT
"""The count-by-type report over a reprocess run's `problems`
(redaction-locate-remaining). Pure unit tests on synthetic input, no DB."""
from __future__ import annotations

import json
import logging

from wordsworth.value_not_located_report import by_type


def test_groups_by_type_with_exact_counts():
    """At least three types, two documents in one type (PERSON)."""
    problems = {
        "doc-1": "value-not-located: PERSON (0 of 1 located)",
        "doc-2": "value-not-located: PERSON (1 of 2 located)",
        "doc-3": "value-not-located: LOCATION (2 of 2 located)",
        "doc-4": "value-not-located: EMAIL (0 of 3 located)",
        # a hard failure, not a value-not-located miss -- not counted here.
        "doc-5": "AnonymizationInvariantError[waarde-overleefde-vervanging]",
    }
    assert by_type(problems) == {
        "PERSON": {"documents": 2, "located": 1, "occurrences": 3},
        "LOCATION": {"documents": 1, "located": 2, "occurrences": 2},
        "EMAIL": {"documents": 1, "located": 0, "occurrences": 3},
    }


def test_empty_problems_yields_empty_report():
    assert by_type({}) == {}


def test_report_and_log_hold_no_value_or_page_text(caplog):
    """Synthetic values and page text in the input must not reach the report's
    output or any captured log record -- only type and counts travel."""
    secret_value = "Jan Jansen"
    secret_page_text = "Geachte heer Jansen, uw aanvraag van 3 maart is"
    problems = {
        "doc-1": "value-not-located: PERSON (0 of 1 located)",
        # these never follow the value-not-located shape, so they are
        # dropped -- but the report must not echo them either way.
        "doc-2": f"AnonymizationInvariantError[waarde-overleefde-vervanging] "
                 f"{secret_value}",
        "doc-3": secret_page_text,
    }
    with caplog.at_level(logging.DEBUG):
        report = by_type(problems)

    out = json.dumps(report)
    assert secret_value not in out and secret_page_text not in out
    assert secret_value not in caplog.text and secret_page_text not in caplog.text
    assert report == {"PERSON": {"documents": 1, "located": 0, "occurrences": 1}}
