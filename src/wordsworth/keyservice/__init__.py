"""The key service (ADR-0009): its own process, settings, database and
schema (`KeyServiceBase`), separate from wordsworth. Nothing in wordsworth
imports this package; nothing here reads `wordsworth.config.settings`.

Ships without traffic in this change (`key-service-skeleton`) -- see
`openspec/changes/key-service-skeleton/proposal.md`.
"""
from __future__ import annotations
