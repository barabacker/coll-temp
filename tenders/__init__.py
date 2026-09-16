"""tenders — bankruptcy-trade collection built on the ``collector`` framework.

Domain layer: the :class:`~tenders.core.lot.Lot` model every engine emits, the
storage contract that persists it, the listing→dive→lot skeleton the engines
share, and the per-site parsers themselves. Everything domain-free (crawling,
HTTP, the registry) lives in the ``collector`` package.

Depends on no Django code: storage is reached through the LotSink interface and
the concrete implementation is injected by the caller.

Importing the platform module is what populates the registry via
``@register_parser`` — keep that import here.
"""

from collector import (
    BaseParser,
    ParserContext,
    ParserNotFound,
    Request,
    Response,
    get_parser,
    register_parser,
    registry,
)

# Side-effect import: builds and registers every parser from platforms.toml.
from tenders import platforms as _platforms  # noqa: F401
from tenders.core.dive import DiveParser
from tenders.core.lot import Lot
from tenders.core.parser import LotParser
from tenders.core.storage.contracts import ChangeStatus
from tenders.core.storage.sink import LotSink
from tenders.runner import CrawlResult, run_parser

__all__ = [
    'BaseParser',
    'ChangeStatus',
    'CrawlResult',
    'DiveParser',
    'Lot',
    'LotParser',
    'LotSink',
    'ParserContext',
    'ParserNotFound',
    'Request',
    'Response',
    'get_parser',
    'register_parser',
    'registry',
    'run_parser',
]
