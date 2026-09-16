"""TenderBtorg derives URLs; the 6 platforms register."""

from __future__ import annotations

from tenders import get_parser, registry
from tenders.sources.btorg.base import TenderBtorg

BTORG_KEYS = {'atctrade', 'ausib', 'etp_profit', 'aukcioncenter', 'regtorg', 'ptp_center'}


def test_all_btorg_platforms_registered():
    assert BTORG_KEYS <= set(registry())


def test_base_url_derived():
    cls = get_parser('atctrade')
    assert issubclass(cls, TenderBtorg)
    assert cls.BASE_URL == 'https://atctrade.ru/etp/trade/list.html'
    assert cls.start_urls == ['https://atctrade.ru/etp/trade/list.html']


def test_no_response_hooks():
    assert get_parser('atctrade').settings.response_hooks == ()
