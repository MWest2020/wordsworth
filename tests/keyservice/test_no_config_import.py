"""design.md "Reuse and imports", rule 2 and the closing line of that
section: "This change itself imports nothing that reads config.settings."
Every test in this directory already runs under the poisoned
``wordsworth.config.settings`` (``conftest.no_wordsworth_config``,
autouse) -- this file proves that poisoning is real and that the service's
own modules survive it."""
from __future__ import annotations

import importlib

import pytest

_KEYSERVICE_MODULES = [
    "wordsworth.keyservice.config",
    "wordsworth.keyservice.models",
    "wordsworth.keyservice.models_access",
    "wordsworth.keyservice.db",
    "wordsworth.keyservice.auth",
    "wordsworth.keyservice.bootstrap",
    "wordsworth.keyservice.serve",
]


def test_poison_is_active():
    from wordsworth.config import settings

    with pytest.raises(AssertionError):
        settings.database_url


@pytest.mark.parametrize("module_name", _KEYSERVICE_MODULES)
def test_keyservice_modules_import_cleanly_under_poisoned_settings(module_name):
    importlib.import_module(module_name)  # must not raise
