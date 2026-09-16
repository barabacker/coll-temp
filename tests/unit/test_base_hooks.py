"""Parsers declare their own HTTP specifics through ``settings``."""

from __future__ import annotations

from collector import BaseParser
from tenders.sources.fogsoft.base import TenderFogsoft
from tenders.sources.fogsoft.inprotect import solve_inprotect


def test_base_parser_defaults():
    assert BaseParser.settings.response_hooks == ()
    assert BaseParser.settings.extra_ca_cert is None
    assert BaseParser.settings.skip_tls_verify is False


def test_fogsoft_declares_inprotect_hook():
    assert TenderFogsoft.settings.response_hooks == (solve_inprotect,)
