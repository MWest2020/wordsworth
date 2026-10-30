# SPDX-License-Identifier: MIT
"""The film's claim filter (tools/film/claims.py): a claim whose check fails is dropped,
and every number in a sentence comes from a check's output. Offline: fake facts, fake
test results, fake commands."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "film"))

import claims  # noqa: E402
import pages  # noqa: E402


def spec(*cs):
    return {"claims": list(cs)}


def by_id(results):
    return {r["id"]: r for r in results}


def no_cmd(cmd):
    raise AssertionError("no command expected")


def test_a_failing_facts_check_drops_the_claim():
    s = spec({"id": "a", "scene": "x", "facts": "documents >= 100", "sentences": ["{documents} docs."]})
    r = claims.resolve(s, {"documents": 12}, None, {}, no_cmd)[0]
    assert r["shown"] is False and "facts check false" in r["why"]
    assert "sentences" not in r


def test_the_number_comes_from_the_facts_output():
    s = spec({"id": "a", "scene": "x", "facts": "documents >= 100", "sentences": ["{documents} docs."]})
    r = claims.resolve(s, {"documents": 415}, None, {}, no_cmd)[0]
    assert r["shown"] and r["sentences"] == ["415 docs."]


def test_no_live_facts_drops_every_facts_claim():
    s = spec({"id": "a", "scene": "x", "facts": "keys > 0", "sentences": ["Keys."]})
    r = claims.resolve(s, None, "ssh: unreachable", {}, no_cmd)[0]
    assert not r["shown"] and "unavailable" in r["why"]


def test_a_missing_fact_is_an_error_not_a_pass():
    s = spec({"id": "a", "scene": "x", "facts": "keys > 0", "sentences": ["Keys."]})
    assert not claims.resolve(s, {"documents": 1}, None, {}, no_cmd)[0]["shown"]


def test_a_failing_or_skipped_test_drops_the_claim():
    s = spec({"id": "a", "scene": "x", "pytest": ["t.py::ok", "t.py::skipped"], "sentences": ["S."]})
    r = claims.resolve(s, None, None, {"t.py::ok": True, "t.py::skipped": False}, no_cmd)[0]
    assert not r["shown"] and "t.py::skipped" in r["why"]


def test_command_output_fills_the_sentence_and_a_failing_command_drops_it():
    s = spec({"id": "lic", "scene": "x", "cmd": "check", "sentences": ["Onder {licence}."]})
    ok = claims.resolve(s, None, None, {}, lambda c: (True, {"licence": "MIT"}, ""))[0]
    assert ok["sentences"] == ["Onder MIT."]
    bad = claims.resolve(s, None, None, {}, lambda c: (False, {"licence": "MIT"}, "mismatch"))[0]
    assert not bad["shown"] and "mismatch" in bad["why"]


def test_a_sentence_without_its_value_is_dropped_not_guessed():
    s = spec({"id": "a", "scene": "x", "cmd": "c", "sentences": ["{q_top2} van {q_total}."]})
    r = claims.resolve(s, None, None, {}, lambda c: (True, {"q_total": 5}, ""))[0]
    assert not r["shown"] and r["why"] == "no value for q_top2"


def test_requires_drops_a_claim_when_the_one_it_rests_on_is_dropped():
    s = spec({"id": "base", "scene": "x", "facts": "n > 0", "sentences": ["Base."]},
             {"id": "why", "scene": "x", "requires": ["base"], "sentences": ["Because."]})
    r = by_id(claims.resolve(s, {"n": 0}, None, {}, no_cmd))
    assert not r["why"]["shown"] and r["why"]["why"] == "requires base"


def test_parse_kv_reads_numbers_as_numbers():
    assert claims.parse_kv("q_total=5\nlicence=MIT\nnoise\n") == {"q_total": 5, "licence": "MIT"}


def test_run_pytest_counts_a_skip_as_not_passed(tmp_path):
    def fake_run(args, **kw):
        xml = next(a for a in args if a.startswith("--junitxml=")).split("=", 1)[1]
        open(xml, "w").write(
            '<testsuites><testsuite><testcase classname="tests.test_a" name="test_ok"/>'
            '<testcase classname="tests.test_a" name="test_skip"><skipped/></testcase>'
            '</testsuite></testsuites>')
    nodes = {"tests/test_a.py::test_ok", "tests/test_a.py::test_skip", "tests/test_a.py::test_gone"}
    got = claims.run_pytest(nodes, cwd=str(tmp_path), run=fake_run)
    assert got == {"tests/test_a.py::test_ok": True, "tests/test_a.py::test_skip": False,
                   "tests/test_a.py::test_gone": False}


def test_the_plan_leaves_out_what_was_dropped():
    resolved = [
        {"id": "pilot-docs", "scene": "bewijs", "shown": True, "sentences": ["415 docs."],
         "values": {"documents": 415}},
        {"id": "pilot-redacted", "scene": "bewijs", "shown": False, "why": "facts check false"},
        {"id": "contact", "scene": "contact", "shown": False, "why": "command failed"},
    ]
    scenes = {s["key"]: s for s in pages.plan(resolved)}
    assert list(scenes) == ["bewijs"]                  # a scene with no proven claim is gone
    b = scenes["bewijs"]
    assert b["captions"] == ["415 docs."] and b["first"] == {"pilot-docs": 0}
    assert "<b>415</b>" in b["html"] and "gelakte pdf" not in b["html"]


def test_every_claim_in_the_film_file_has_a_check_and_a_known_scene():
    import yaml

    spec_ = yaml.safe_load(open(claims.CLAIMS, encoding="utf-8"))
    keys = {s["key"] for s in pages.SCENES}
    for c in spec_["claims"]:
        assert c["scene"] in keys, c["id"]
        assert {"facts", "pytest", "cmd", "requires"} & set(c), c["id"]


def test_only_the_values_a_sentence_uses_are_kept():
    s = spec({"id": "a", "scene": "x", "facts": "documents > 0", "sentences": ["{documents} docs."]})
    r = claims.resolve(s, {"documents": 415, "audit_records": 8767}, None, {}, no_cmd)[0]
    assert r["values"] == {"documents": 415}


def test_a_reworded_drop_reason_is_the_same_film(tmp_path):
    import json

    base = [{"id": "a", "scene": "x", "shown": True, "sentences": ["S."], "values": {}}]
    a, b, c = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "c.json"
    a.write_text(json.dumps(base + [{"id": "b", "scene": "x", "shown": False, "why": "timeout 3s"}]))
    b.write_text(json.dumps(base + [{"id": "b", "scene": "x", "shown": False, "why": "timeout 4s"}]))
    c.write_text(json.dumps([{**base[0], "sentences": ["T."]}]))
    assert claims.same(a, b) and not claims.same(a, c)
