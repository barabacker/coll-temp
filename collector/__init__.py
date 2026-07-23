"""collector — Django-free scraping engine.

Async Spider-style core, parser registry, HTTP layer, and per-engine parsers.
Depends on no Django code: storage is reached through the LotSink interface
(collector.sink), and the concrete implementation is injected by the caller.

Importing the platform modules is what populates the registry via
``@register_parser`` — keep those imports here.
"""

from collector.core.spider import BaseParser, ParserContext, Request, Response

# Side-effect import: builds and registers every parser from platforms.toml.
from collector import platforms as _platforms  # noqa: E402,F401
from collector.core.registry import ParserNotFound, get_parser, register_parser, registry
from collector.runner import CrawlResult, run_parser
from collector.core.storage.sink import LotSink

__all__ = [
    'BaseParser',
    'ParserContext',
    'Request',
    'Response',
    'LotSink',
    'ParserNotFound',
    'get_parser',
    'register_parser',
    'registry',
    'CrawlResult',
    'run_parser',
]
