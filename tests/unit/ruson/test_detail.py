"""parse_lots against the rus-on trade_view detail fixture."""

from __future__ import annotations

from pathlib import Path

from parsel import Selector

from collector.sources.ruson.parsing.detail import parse_lots

FIXTURE = Path(__file__).parents[2] / 'fixtures' / 'ruson' / 'nistp_detail.html'

TRADE = {
    'trade_id': '68240',
    'trade_nid': '484796',
    'trade_number': '68240-ОАОФ',
    'trade_type': 'ОАОФ',
    'detail_url': 'https://nistp.ru/bankrot/trade_view.php?trade_nid=484796',
    '_source': 'nistp',
}


def _sel() -> Selector:
    return Selector(text=FIXTURE.read_text(encoding='utf-8'))


def test_parse_lots_first_lot():
    lots = parse_lots(_sel(), TRADE)
    assert lots
    first = lots[0]
    assert first['lot_id'] == '68240_1'
    assert first['lot_num'] == '1'
    assert first['price'] == 1315000.0
    assert first['status'] == 'Торги объявлены'
    assert first['bidding_date'] == '28.08.2026 15:00:00'
    assert first['event_date'] == '23.07.2026 15:00:00'
    assert first['trade_title'] == '68240-ОАОФ'
    assert first['_source'] == 'nistp'
    assert first['detail']


def test_parse_lots_ignores_prose_mentioning_lot_number():
    """Prose ("…задаток, Лот № 1, должник…") must not be taken for a lot header.

    Regression: such a paragraph produced a phantom second lot with the same
    lot_id and no price — the source of the duplicate/null-price rows in the
    collected data.
    """
    fixture = Path(__file__).parents[2] / 'fixtures' / 'ruson' / 'nistp_detail_prose_lot.html'
    sel = Selector(text=fixture.read_text(encoding='utf-8'))
    lots = parse_lots(sel, {'trade_id': '68289', 'trade_number': '68289-ОАОФ', '_source': 'nistp'})
    assert len(lots) == 1
    assert lots[0]['lot_id'] == '68289_1'
    assert lots[0]['price'] == 140000.0


def test_parse_lots_promkonsalt_variant():
    # promkonsalt: plain <td> label/value (no class="label") and span.lot_title
    # instead of a <th> "Лот №" marker.
    fixture = Path(__file__).parents[2] / 'fixtures' / 'ruson' / 'promkonsalt_detail.html'
    sel = Selector(text=fixture.read_text(encoding='utf-8'))
    lots = parse_lots(sel, {'trade_id': '3179', 'trade_number': '3179-ОАОФ', '_source': 'promkonsalt'})
    assert lots
    first = lots[0]
    assert first['lot_id'] == '3179_1'
    assert first['price'] == 17550000.0
    assert first['status'] == 'Торги объявлены'
    assert first['description']
