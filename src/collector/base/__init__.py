"""Spider-style parser base classes: Request/Response/ParserContext/BaseParser."""

from __future__ import annotations

from collector.base.context import ParserContext
from collector.base.parser import BaseParser
from collector.base.request import Request
from collector.base.response import Response

__all__ = ['BaseParser', 'ParserContext', 'Request', 'Response']
