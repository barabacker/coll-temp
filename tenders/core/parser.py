"""LotParser — the framework parser taught to persist lots.

``collector.BaseParser`` counts items and nothing else; this subclass is where
the domain's storage contract enters: every emitted :class:`~tenders.core.lot.Lot`
goes to the injected :class:`~tenders.core.storage.sink.LotSink`, and the
NEW/CHANGED outcome is tallied for the job report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from collector import BaseParser, ParserContext

from tenders.core.storage.contracts import ChangeStatus

if TYPE_CHECKING:
    from tenders.core.lot import Lot


class LotParser(BaseParser):
    """A parser whose items are lots, persisted through ``ctx.sink``."""

    def __init__(self, ctx: ParserContext) -> None:
        super().__init__(ctx)
        self.new_item_count = 0
        self.changed_item_count = 0

    async def process_item(self, item: Lot) -> None:
        """Count lots and, if a sink is configured, persist them."""
        await super().process_item(item)
        if self.ctx.sink is not None:
            status = await self.ctx.sink.save(item)
            if status == ChangeStatus.NEW:
                self.new_item_count += 1
            elif status == ChangeStatus.CHANGED:
                self.changed_item_count += 1
