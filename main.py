"""Локальный запуск одного парсера площадки — посмотреть, что собирается.

Песочница: движок collector (src/collector) без Django. Хранилище здесь —
простой CollectingSink, который копит лоты в память и пишет их в lots.json.
В боевом проекте вместо него ORM-реализация, пишущая в Postgres.

Использование:
    uv run python main.py                 # centerr, 1 страница
    uv run python main.py alfalot         # другой парсер, 1 страница
    uv run python main.py zakazrf 2       # парсер + число страниц
    uv run python main.py --list          # показать все ключи парсеров

ВНИМАНИЕ: это реальные внешние сайты. Держи число страниц малым.
"""

import json
import logging
import sys
from pathlib import Path

# src/ на путь импорта, чтобы работал `import collector`.
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from collector import ParserNotFound, get_parser, registry, run_parser  # noqa: E402
from collector.core.storage.contracts import ChangeStatus  # noqa: E402


class CollectingSink:
    """Минимальная реализация интерфейса collector.sink.LotSink.

    Копит лоты в памяти. get_fingerprints возвращает пусто => каждый лот
    считается новым и парсер ныряет в его detail-страницу, так что в собранных
    лотах будут и detail-поля (секции, вложения, график цены).
    """

    def __init__(self):
        self.items = []

    async def get_fingerprints(self, source, lot_ids):
        return {}

    async def save(self, item):
        self.items.append(item)
        return ChangeStatus.NEW


def main():
    args = sys.argv[1:]

    if '--list' in args:
        print('Доступные парсеры:')
        for key in sorted(registry()):
            print('  ', key)
        return

    key = args[0] if args else 'centerr'
    max_pages = args[1] if len(args) > 1 else '1'

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    try:
        parser_cls = get_parser(key)
    except ParserNotFound:
        print(f'Нет парсера "{key}". Список: uv run python main.py --list')
        raise SystemExit(1) from None

    sink = CollectingSink()
    print(f'=== {key}: обход, max_pages={max_pages} ===\n')
    result = run_parser(parser_cls, params={'max_pages': str(max_pages)}, sink=sink)

    out = Path(__file__).parent / 'lots.json'
    out.write_text(json.dumps(sink.items, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'\n=== собрано {result.total} лотов -> {out.name} ===')
    for item in sink.items[:5]:
        price = item.get('price')
        print(f'- {item.get("lot_id"):20} | {(item.get("trade_title") or "")[:46]:46} | {price}')


if __name__ == '__main__':
    main()
