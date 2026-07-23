"""Which trade statuses count as live (drives the stop-at-archive rule)."""

from __future__ import annotations

import pytest

from collector.core.parsing import is_active_status, pick_status, read_only_active


@pytest.mark.parametrize(
    'status',
    [
        'Торги объявлены',
        'Идет прием заявок',
        'идёт приём заявок',
        'Объявлен',
        'Прием ценовых предложений',
        'На утверждении',
        None,
        '',
        'какой-то новый статус',  # unknown -> live, never truncate on doubt
    ],
)
def test_live_statuses(status):
    assert is_active_status(status) is True


@pytest.mark.parametrize(
    'status',
    [
        'Торги завершены',
        'Прием заявок завершен',  # contains "прием заявок" but is finished
        'Торги отменены',
        'Торги приостановлены',
        'Торги состоялись',
        'Торги не состоялись',
    ],
)
def test_finished_statuses(status):
    assert is_active_status(status) is False


def test_pick_status_finds_the_status_cell():
    cells = [
        '68240-ОАОФ',
        'Чахоян Кима Самвеловна',
        'Очень длинное описание предмета торгов, которое статусом не является '
        'и потому должно быть пропущено',
        'Торги объявлены',
    ]
    assert pick_status(cells) == 'Торги объявлены'
    assert pick_status(['12345-ОАОФ', 'Иванов И.И.']) is None


def test_read_only_active_defaults_on_and_can_be_disabled():
    assert read_only_active({}) is True
    assert read_only_active({'only_active': '1'}) is True
    assert read_only_active({'only_active': '0'}) is False
    assert read_only_active({'only_active': 'false'}) is False
