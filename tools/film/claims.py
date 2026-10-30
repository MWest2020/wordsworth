"""Resolve the film's claims: run every check, keep a claim only when its check passes
today, and fill its sentences from the check's output (docs/reference/film-claims.yml).

    python3 tools/film/claims.py <out.json>     -> writes the resolved claims, prints a summary
    python3 tools/film/claims.py --same A B     -> exit 0 when A and B make the same film

The output keeps the dropped claims too, each with the reason, so a build says why a
sentence is missing. Nothing here renders; tools/film/build.sh does that."""
import json
import os
import string
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLAIMS = os.path.join(ROOT, "docs", "reference", "film-claims.yml")


def parse_kv(text):
    """`key=value` lines from a check's stdout; numbers become ints."""
    out = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            v = v.strip()
            out[k.strip()] = int(v) if v.lstrip("-").isdigit() else v
    return out


def run_cmd(cmd, cwd=ROOT, run=subprocess.run):
    p = run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=600)
    return p.returncode == 0, parse_kv(p.stdout), (p.stderr or p.stdout).strip()[-200:]


def run_pytest(nodes, cwd=ROOT, run=subprocess.run):
    """{node id: passed?}; a skipped or erroring test is not a pass."""
    if not nodes:
        return {}
    with tempfile.TemporaryDirectory() as t:
        xml = os.path.join(t, "junit.xml")
        run(["uv", "run", "-q", "pytest", "-q", "-p", "no:cacheprovider",
             f"--junitxml={xml}", *sorted(nodes)], cwd=cwd, capture_output=True, text=True)
        if not os.path.exists(xml):
            return {n: False for n in nodes}
        seen = {}
        for case in ET.parse(xml).getroot().iter("testcase"):
            node = case.get("classname", "").replace(".", "/") + ".py::" + case.get("name", "")
            seen[node] = not any(c.tag in ("failure", "error", "skipped") for c in case)
    return {n: seen.get(n, False) for n in nodes}


def names(sentences):
    return {f for s in sentences for _, f, _, _ in string.Formatter().parse(s) if f}


def fill(sentences, values):
    """The sentences with their `{name}`s filled, or (None, the missing names)."""
    missing = sorted(n for n in names(sentences) if n not in values)
    if missing:
        return None, missing
    return [s.format(**values) for s in sentences], []


def resolve(spec, facts, facts_err, pytest_results, cmd_runner=run_cmd):
    """Every claim with `shown` true/false and, when dropped, `why`."""
    out, by_id = [], {}
    for c in spec["claims"]:
        values, why = {}, None
        if "facts" in c:
            if facts is None:
                why = f"live facts unavailable: {facts_err}"
            else:
                try:
                    if not eval(c["facts"], {"__builtins__": {}}, dict(facts)):
                        why = f"facts check false: {c['facts']}"
                except Exception as exc:  # a fact the probe didn't return
                    why = f"facts check error: {exc}"
                values.update(facts)
        if why is None and c.get("pytest"):
            failed = [n for n in c["pytest"] if not pytest_results.get(n)]
            if failed:
                why = "test not passed: " + ", ".join(failed)
        if why is None and "cmd" in c:
            ok, kv, err = cmd_runner(c["cmd"])
            values.update(kv)
            if not ok:
                why = f"command failed: {c['cmd']} ({err})"
        if why is None:
            gone = [r for r in c.get("requires", []) if not by_id.get(r, {}).get("shown")]
            if gone:
                why = "requires " + ", ".join(gone)
        sentences = None
        if why is None:
            sentences, missing = fill(c["sentences"], values)
            if missing:
                why = "no value for " + ", ".join(missing)
        r = {"id": c["id"], "scene": c["scene"], "shown": why is None}
        if why is None:
            r["sentences"] = sentences
            # only the values a sentence uses: a build is "unchanged" while what the
            # film says is, however other live counts move
            r["values"] = {k: values[k] for k in sorted(names(c["sentences"]))}
        else:
            r["why"] = why
        out.append(r)
        by_id[c["id"]] = r
    return out


def live_facts(cmd):
    p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip()[-200:]
    try:
        return json.loads(p.stdout.strip().splitlines()[-1]), None
    except (ValueError, IndexError):
        return None, "probe printed no JSON"


def film_says(results):
    """What the film says: the shown claims and their sentences (a dropped claim's
    reason may word itself differently each day without changing the film)."""
    return [(r["id"], r["sentences"]) for r in results if r["shown"]]


def same(a, b):
    load = lambda p: film_says(json.load(open(p, encoding="utf-8")))  # noqa: E731
    return load(a) == load(b)


def main(path):
    spec = yaml.safe_load(open(CLAIMS, encoding="utf-8"))
    facts, err = live_facts(spec["live_facts_cmd"])
    nodes = {n for c in spec["claims"] for n in c.get("pytest", [])}
    results = resolve(spec, facts, err, run_pytest(nodes))
    json.dump(results, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for r in results:
        print(("shown  " if r["shown"] else "DROPPED") + f" {r['id']}" + ("" if r["shown"] else f": {r['why']}"))


if __name__ == "__main__":
    if sys.argv[1] == "--same":
        sys.exit(0 if same(sys.argv[2], sys.argv[3]) else 1)
    main(sys.argv[1])
