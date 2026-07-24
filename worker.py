"""Worker: run platform parsers and dump collected lots to data/<key>.json.

One JSON file per site (parser key). Full crawl by default (all listing pages,
diving into every trade's detail); pass --max-pages to cap for a quick run.

Usage:
    uv run python worker.py                     # all registered parsers, full crawl
    uv run python worker.py nistp sistematorg   # only these keys
    uv run python worker.py --max-pages 2       # cap pages per site
    uv run python worker.py --concurrency 6     # sites scraped in parallel
    uv run python worker.py --engine kendo      # only one engine's keys (by module)
    uv run python worker.py --list              # show available keys and exit

WARNING: these are real external sites. A full run of every site fetches every
listing page and every detail page — potentially many thousands of requests.
Start with a small --max-pages and a few keys.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collector import get_parser, registry  # noqa: E402
from collector.core.lot import Lot  # noqa: E402
from collector.core.spider import ParserContext  # noqa: E402
from collector.core.storage.contracts import ChangeStatus  # noqa: E402
from collector.http.factory import build_http_client  # noqa: E402

logger = logging.getLogger('worker')


class CollectingSink:
    """Accumulates every emitted lot in memory (no change detection).

    ``get_fingerprints`` returns empty so every lot is treated as NEW and the
    parser dives into each detail page — i.e. a full collection.
    """

    def __init__(self) -> None:
        self.items: list[Lot] = []

    async def get_fingerprints(self, source: str, lot_ids: object) -> dict[str, str]:
        return {}

    async def save(self, item: Lot) -> ChangeStatus:
        self.items.append(item)
        return ChangeStatus.NEW


@dataclass(slots=True)
class SiteResult:
    key: str
    items: int
    duration: float
    error: str | None = None


async def _run_site(key: str, params: dict[str, str], out_dir: Path, sem: asyncio.Semaphore) -> SiteResult:
    async with sem:
        started = time.monotonic()
        parser_cls = get_parser(key)
        sink = CollectingSink()

        async def _log(message: str) -> None:
            logger.info('[%s] %s', key, message)

        try:
            http = build_http_client(parser_cls)
            async with http:
                ctx = ParserContext(http=http, params=params, lot_sink=sink, log=_log)
                parser = parser_cls(ctx)
                await parser.crawl()
        except Exception as exc:  # noqa: BLE001 — isolate one site's failure
            return SiteResult(key, len(sink.items), time.monotonic() - started, error=repr(exc))

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f'{key}.json'
        out_path.write_text(
            json.dumps(
                [lot.model_dump(mode='json') for lot in sink.items],
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        return SiteResult(key, len(sink.items), time.monotonic() - started)


async def _run_all(keys: list[str], params: dict[str, str], out_dir: Path, concurrency: int) -> list[SiteResult]:
    sem = asyncio.Semaphore(concurrency)
    tasks = [_run_site(key, params, out_dir, sem) for key in keys]
    return await asyncio.gather(*tasks)


def _keys_for_engine(engine: str) -> list[str]:
    """Registered keys whose parser class lives in collector.sources.<engine>."""
    prefix = f'collector.sources.{engine}.'
    return sorted(k for k, cls in registry().items() if cls.__module__.startswith(prefix))


def main() -> None:
    parser = argparse.ArgumentParser(description='Run parsers and dump lots to data/<key>.json')
    parser.add_argument('keys', nargs='*', help='parser keys to run (default: all)')
    parser.add_argument('--engine', help='run only keys from this engine (kendo, btorg, ruson, fogsoft)')
    parser.add_argument(
        '--max-pages',
        type=int,
        default=200,
        help='safety cap on listing pages per site (default: 200; 0 = no cap). '
        'Listing pages are cheap — only live trades are actually fetched.',
    )
    parser.add_argument(
        '--all-lots',
        action='store_true',
        help='also collect finished/cancelled lots (by default only live trades '
        'are fetched, while the listing is still paged through)',
    )
    parser.add_argument('--concurrency', type=int, default=4, help='sites scraped in parallel (default: 4)')
    parser.add_argument('--out', default='data', help='output directory (default: data)')
    parser.add_argument('--list', action='store_true', help='list available keys and exit')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')
    # Quiet the per-request HTTP hook chatter; keep parser page/detail lines.
    logging.getLogger('collector.http.hooks').setLevel(logging.WARNING)

    all_keys = sorted(registry())
    if args.list:
        print('Available keys:')
        for k in all_keys:
            print('  ', k)
        return

    if args.engine:
        keys = _keys_for_engine(args.engine)
    elif args.keys:
        keys = args.keys
    else:
        keys = all_keys

    unknown = [k for k in keys if k not in registry()]
    if unknown:
        print(f'Unknown keys: {unknown}. Use --list.', file=sys.stderr)
        raise SystemExit(1)

    params: dict[str, str] = {}
    if args.max_pages:
        params['max_pages'] = str(args.max_pages)
    if args.all_lots:
        params['only_active'] = '0'

    out_dir = Path(args.out)
    scope = 'all lots (incl. archive)' if args.all_lots else 'live lots only'
    print(
        f'=== running {len(keys)} site(s), {scope}, '
        f'max_pages={args.max_pages}, concurrency={args.concurrency} ==='
    )
    started = time.monotonic()
    results = asyncio.run(_run_all(keys, params, out_dir, args.concurrency))
    elapsed = time.monotonic() - started

    print('\n=== summary ===')
    ok = 0
    total_items = 0
    for r in sorted(results, key=lambda r: r.key):
        if r.error:
            print(f'  {r.key:16} ERROR ({r.duration:5.1f}s) {r.error[:70]}')
        else:
            ok += 1
            total_items += r.items
            print(f'  {r.key:16} {r.items:6} lots -> {out_dir}/{r.key}.json ({r.duration:5.1f}s)')
    print(f'\n{ok}/{len(results)} sites OK, {total_items} lots total, {elapsed:.1f}s wall')


if __name__ == '__main__':
    main()
