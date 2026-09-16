"""Bridge between the parser core and the synchronous caller (CLI or RQ task).

``collector.run_parser`` hands back the finished parser; this wraps it in the
lot-shaped result the job report expects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import collector

from tenders.core.parser import LotParser
from tenders.core.storage.sink import LotSink

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlResult:
    total: int
    new: int
    changed: int


def run_parser(
    parser_cls: type[LotParser],
    *,
    params: dict[str, str] | None = None,
    sink: LotSink | None = None,
) -> CrawlResult:
    """Run a parser to completion synchronously. Called from the RQ task.

    ``sink`` is injected by the caller (the Django side passes an ORM sink).
    Passing ``None`` runs the crawl without persisting — useful for a smoke
    check that hits the site but writes nothing.
    """

    async def _log(message: str) -> None:
        logger.info('[%s] %s', parser_cls.name, message)

    parser = collector.run_parser(parser_cls, params=params, sink=sink, log=_log)
    return CrawlResult(
        total=parser.item_count,
        new=parser.new_item_count,
        changed=parser.changed_item_count,
    )
