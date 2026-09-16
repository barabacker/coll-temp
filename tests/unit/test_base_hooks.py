"""Parsers declare their own HTTP specifics via class attributes."""

from __future__ import annotations

from collector import BaseParser
from tenders.sources.fogsoft.base import TenderFogsoft
from tenders.sources.fogsoft.inprotect import solve_inprotect


def test_base_parser_defaults():
    assert BaseParser.RESPONSE_HOOKS == ()
    assert BaseParser.EXTRA_CA_CERT is None
    assert BaseParser.SKIP_TLS_VERIFY is False


def test_fogsoft_declares_inprotect_hook():
    assert TenderFogsoft.RESPONSE_HOOKS == (solve_inprotect,)
