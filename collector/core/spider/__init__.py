"""Spider-style parser base classes: Request/Response/ParserContext/BaseParser."""

from __future__ import annotations

from collector.core.spider.context import ParserContext
from collector.core.spider.dive import DiveParser
from collector.core.spider.parser import BaseParser
from collector.core.spider.request import Request
from collector.core.spider.response import Response

__all__ = ['BaseParser', 'DiveParser', 'ParserContext', 'Request', 'Response']
