"""TenderRuson derives URLs (incl. per-site LISTING_PATH); 5 platforms register."""

from __future__ import annotations

from tenders import get_parser, registry
from tenders.sources.ruson.base import TenderRuson

RUSON_KEYS = {'nistp', 'el_torg', 'rus_on', 'sistematorg', 'promkonsalt'}


def test_all_ruson_platforms_registered():
    assert RUSON_KEYS <= set(registry())


def test_base_url_default_path():
    cls = get_parser('nistp')
    assert issubclass(cls, TenderRuson)
    assert cls.BASE_URL == 'https://nistp.ru/bankrot/trade_list.php'


def test_base_url_tradelist_variant():
    cls = get_parser('sistematorg')
    assert cls.BASE_URL == 'https://sistematorg.com/tradelist.php'


def test_no_response_hooks():
    assert get_parser('nistp').settings.response_hooks == ()
