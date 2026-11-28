"""design.md "Modules" and AGENTS.md's 200-line invariant: seal stays in
``api_originals.py``, open lives in ``api_open.py`` -- the reviewer's FAIL on
wordsworth#544 was a combined ``api_originals.py`` at 202 lines. Both
deletions stay in ``api_documents.py``, the key-lifecycle chain in
``lifecycle.py`` (design.md "Modules", ``key-service-delete``)."""
from __future__ import annotations

from pathlib import Path

import wordsworth.keyservice.api_documents as api_documents
import wordsworth.keyservice.api_metrics as api_metrics
import wordsworth.keyservice.api_open as api_open
import wordsworth.keyservice.api_originals as api_originals
import wordsworth.keyservice.api_reveal as api_reveal
import wordsworth.keyservice.config as config
import wordsworth.keyservice.doc_keys as doc_keys
import wordsworth.keyservice.grants as grants
import wordsworth.keyservice.identity as identity
import wordsworth.keyservice.lifecycle as lifecycle
import wordsworth.keyservice.limits as limits
import wordsworth.keyservice.reveal_gate as reveal_gate
import wordsworth.keyservice.reveal_resolve as reveal_resolve
import wordsworth.keyservice.roles as roles
import wordsworth.keyservice.state as state

_CHECKED = [doc_keys, api_originals, api_open, api_documents, lifecycle,
           config, state, limits, api_metrics, api_reveal, reveal_gate,
           reveal_resolve, identity, roles, grants]


def _line_count(module) -> int:
    return len(Path(module.__file__).read_text().splitlines())


def test_each_module_is_at_most_200_lines():
    over = {m.__name__: n for m in _CHECKED if (n := _line_count(m)) > 200}
    assert over == {}


def test_seal_is_defined_in_api_originals_not_api_open():
    assert hasattr(api_originals, "seal")
    assert not hasattr(api_open, "seal")
    source = Path(api_open.__file__).read_text()
    assert '"/v1/originals/{document_id}/seal"' not in source


def test_open_is_defined_in_api_open_not_api_originals():
    assert hasattr(api_open, "open_original")
    assert not hasattr(api_originals, "open_original")
    source = Path(api_originals.__file__).read_text()
    assert '"/v1/originals/{document_id}/open"' not in source
