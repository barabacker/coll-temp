"""The Lot model standardizes and normalizes an emitted parser item."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from collector.core.lot import Lot

# A maximal (fogsoft-shaped) emitted item — every one of the 17 keys.
FULL_ITEM = {
    'lot_id': '0099382_1',
    'trade_id': '0099382',
    'trade_number': '0099382',
    'lot_num': '1',
    'debtor': 'Багаутдинова Рузиля Вазировна',
    'trade_type': 'Открытый аукцион',
    'organizer': 'Климова Светлана Евгеньевна',
    'description': 'Право собственности на объект недвижимости',
    'lot_url': '/public/auctions/lots/view/1167819/',
    'price': 5500800.0,
    'price_raw': '5 500 800,00',
    'status': 'Прием заявок',
    'bidding_date': '26.08.2026 12:30 (33 дн.)',
    'event_date': '27.08.2026 11:30',
    'detail': {'Информация о лоте №1': {'Наименование': 'X'}},
    'attachments': [{'name': 'doc.pdf', 'url': 'http://x/doc.pdf'}],
    'price_schedule': [{'период': '1', 'цена': '100'}],
    '_source': 'centerr',
}

# A minimal (btorg/ruson-shaped) item — no attachments / price_schedule.
MINIMAL_ITEM = {
    'lot_id': '68289_1',
    'trade_id': '68289',
    'trade_number': '68289-ОАОФ',
    'lot_num': '1',
    'debtor': 'ООО "Ромашка"',
    'trade_type': 'ОАОФ',
    'organizer': None,
    'description': 'Легковой автомобиль',
    'lot_url': 'https://nistp.ru/bankrot/trade_view.php?trade_nid=1',
    'price': 140000.0,
    'price_raw': '140 000.00',
    'status': 'Торги завершены',
    'bidding_date': '28.08.2026 00:00:00',
    'event_date': '24.07.2026 00:00:00',
    'detail': {'Номер лота': '1'},
    '_source': 'nistp',
}


def test_full_item_normalized():
    lot = Lot.model_validate(FULL_ITEM)
    assert lot.source == 'centerr'
    assert lot.lot_id == '0099382_1'
    assert lot.trade_number == '0099382'
    assert lot.debtor == 'Багаутдинова Рузиля Вазировна'
    assert lot.organizer == 'Климова Светлана Евгеньевна'
    assert lot.price == 5500800.0
    # dates normalized, raw kept
    assert lot.bidding_deadline == datetime(2026, 8, 26, 12, 30)
    assert lot.bidding_date_raw == '26.08.2026 12:30 (33 дн.)'
    assert lot.result_date == datetime(2026, 8, 27, 11, 30)
    # status -> is_active
    assert lot.is_active is True
    # raw blob folded into extra
    assert lot.extra == {'Информация о лоте №1': {'Наименование': 'X'}}
    assert lot.attachments and lot.price_schedule


def test_minimal_item_defaults_and_finished_status():
    lot = Lot.model_validate(MINIMAL_ITEM)
    assert lot.attachments == []
    assert lot.price_schedule == []
    assert lot.is_active is False  # "Торги завершены"
    assert lot.trade_number == '68289-ОАОФ'
    assert lot.debtor == 'ООО "Ромашка"'
    assert lot.bidding_deadline == datetime(2026, 8, 28, 0, 0)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Lot.model_validate({**MINIMAL_ITEM, 'surprise': 'boom'})


def test_model_dump_is_json_ready():
    dumped = Lot.model_validate(FULL_ITEM).model_dump(mode='json')
    assert dumped['source'] == 'centerr'
    assert dumped['bidding_deadline'] == '2026-08-26T12:30:00'
    assert 'extra' in dumped and '_source' not in dumped
