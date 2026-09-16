"""Response — wraps the result of ``HttpClient.request()``."""

from __future__ import annotations

from typing import Any

from parsel import Selector

from collector.spider.request import Request


class Response:
    """Wraps the result of HttpClient.request().

    curl_cffi's AsyncSession returns an already-materialised response
    (``.text`` / ``.status_code`` are plain attributes, not coroutines), so
    ``text`` / ``status`` are plain attributes here too.
    """

    def __init__(self, raw: Any, request: Request) -> None:
        self.request = request
        self.metadata = request.metadata
        self.status: int = raw.status_code
        self.text: str = raw.text
        self._raw = raw

    @property
    def raw(self) -> Any:
        """The underlying client response, for anything this wrapper omits."""
        return self._raw

    def selector(self) -> Selector:
        return Selector(text=self.text)
