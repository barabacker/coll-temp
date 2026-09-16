"""Behavior held invariant across the restructure: the ``tenders`` facade and
the populated parser registry. Must stay green at every step."""

from __future__ import annotations

import tenders

EXPECTED_KEYS = {
    'centerr', 'alfalot', 'etpu_bankrupt', 'bep', 'arbbitlot', 'arbitat',
    'utp_lot', 'tender_one', 'etpugra', 'tendergarant', 'yuzhnyy_etp',
    'meta_invest', 'gloria_service', 'zakazrf', 'etb',
    'trade_alliance', 'seltim', 'electro_torgi', 'torgi82', 'vetp',
    'atctrade', 'ausib', 'etp_profit', 'aukcioncenter', 'regtorg', 'ptp_center',
    'nistp', 'el_torg', 'rus_on', 'sistematorg', 'promkonsalt',
}


def test_facade_exports_are_importable():
    for name in (
        'BaseParser', 'ParserContext', 'Request', 'Response', 'LotSink',
        'ParserNotFound', 'get_parser', 'register_parser', 'registry',
        'CrawlResult', 'run_parser', 'Lot', 'LotParser', 'DiveParser',
        'ChangeStatus',
    ):
        assert hasattr(tenders, name), f'missing facade export: {name}'


def test_registry_is_fully_populated():
    assert set(tenders.registry()) == EXPECTED_KEYS


def test_get_parser_resolves_a_known_key():
    cls = tenders.get_parser('centerr')
    assert cls.name == 'centerr'
