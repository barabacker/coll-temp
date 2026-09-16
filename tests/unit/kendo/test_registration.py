"""TenderKendo derives URLs; the 5 platforms register."""

from __future__ import annotations

from collector import get_parser, registry
from tenders.sources.kendo.base import TenderKendo

KENDO_KEYS = {'trade_alliance', 'seltim', 'electro_torgi', 'torgi82', 'vetp'}


def test_all_kendo_platforms_registered():
    assert KENDO_KEYS <= set(registry())


def test_base_url_derived():
    cls = get_parser('trade_alliance')
    assert issubclass(cls, TenderKendo)
    assert cls.BASE_URL == 'https://trade-alliance.ru/lots'
    assert cls.start_urls == ['https://trade-alliance.ru/lots']


def test_no_response_hooks():
    cls = get_parser('trade_alliance')
    assert cls.RESPONSE_HOOKS == ()
