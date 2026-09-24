# SPDX-License-Identifier: MIT
"""Every console script starts, in a fresh interpreter.

In one pytest process modules are already imported in whatever order earlier
tests left them, so an import cycle that only breaks when a process enters
through a particular module stays invisible. On 2026-09-24 `import
wordsworth.pipeline` had been failing in any fresh process since 2026-09-22,
and `wordsworth-dedupe` was the first command to hit it -- in the cluster, not
here. Each entry point gets its own interpreter, so the order is the real one.
"""
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_SCRIPTS = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
)["project"]["scripts"]


@pytest.mark.parametrize("name", sorted(_SCRIPTS))
def test_the_entry_point_imports_on_its_own(name):
    module, func = _SCRIPTS[name].split(":")
    r = subprocess.run([sys.executable, "-c", f"import {module}; {module}.{func}"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"{name} ({module}) does not start:\n{r.stderr[-800:]}"


def test_the_pipeline_imports_first():
    """The module the cycle ran through, entered first."""
    r = subprocess.run([sys.executable, "-c", "import wordsworth.pipeline"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
