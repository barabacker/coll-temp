"""Params are strings from the outside world: forgiving readers, sane defaults."""

from __future__ import annotations

import pytest

from collector import read_concurrency, read_flag, read_max_pages


@pytest.mark.parametrize(
    ('params', 'expected'),
    [
        ({}, None),
        ({'max_pages': ''}, None),
        ({'max_pages': '3'}, 3),
        ({'max_pages': '0'}, None),
        ({'max_pages': '-2'}, None),
        ({'max_pages': 'abc'}, None),
    ],
)
def test_read_max_pages(params, expected):
    assert read_max_pages(params) == expected


@pytest.mark.parametrize(
    ('params', 'expected'),
    [
        ({}, 4),
        ({'concurrency': ''}, 4),
        ({'concurrency': '8'}, 8),
        ({'concurrency': '0'}, 4),
        ({'concurrency': 'many'}, 4),
    ],
)
def test_read_concurrency_falls_back_to_the_default(params, expected):
    assert read_concurrency(params, 4) == expected


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [('0', False), ('false', False), ('No', False), ('OFF', False), ('1', True), ('yes', True)],
)
def test_read_flag(raw, expected):
    assert read_flag({'live': raw}, 'live', True) is expected


def test_read_flag_default_when_unset():
    assert read_flag({}, 'live', False) is False
    assert read_flag({'live': ''}, 'live', True) is True
