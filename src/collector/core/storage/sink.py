"""LotSink — the storage interface the parsers depend on.

The engine core stays storage-agnostic: it knows only this Protocol. Concrete
implementations (e.g. the Django ORM sink) live outside this package and are
injected at runtime — see platforms/storage.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from collector.core.storage.contracts import ChangeStatus


class LotSink(Protocol):
    """What a parser needs to persist lots and detect changes."""

    async def save(self, item: dict[str, Any]) -> ChangeStatus:
        """Upsert a lot, returning NEW / CHANGED / UNCHANGED."""
        ...

    async def get_fingerprints(self, source: str, lot_ids: Sequence[str]) -> dict[str, str]:
        """Batch-read current fingerprints for the given lot ids."""
        ...
