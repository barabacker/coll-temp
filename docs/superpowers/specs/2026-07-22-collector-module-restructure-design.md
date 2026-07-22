# Дизайн: реструктуризация модулей `collector` в слои

**Дата:** 2026-07-22
**Статус:** утверждён к реализации
**Поглощает:** `2026-07-22-runner-fogsoft-decoupling-design.md` — механизм развязки
`runner ↔ fogsoft` целиком входит сюда как часть §5.

---

## 1. Цель и контекст

`collector` — асинхронный движок парсеров тендерных площадок, отвязанный от
Django. Расслоение по зависимостям выдержано (ядро знает про хранилище только
через `LotSink`, `registry` не знает про ORM, парсеры не знают про транспорт),
но **файловая раскладка это не показывает**:

- корень смешанный — одиночные файлы (`contracts.py`, `registry.py`, `sink.py`,
  `runner.py`) лежат рядом с пакетами (`base/`, `http/`, `fogsoft/`);
- `runner.py` совмещает 4 concern'а: TLS-утилиту, сборку HTTP-клиента
  (сцеплённую с fogsoft), синхронный мост и result-контракт;
- fogsoft-специфичный хук `solve_inprotect` лежит в generic-слое
  `http/hooks/`, импортируя вниз в `fogsoft`;
- `fogsoft/` — брат ядра, без namespace «один движок из многих».

**Цель:** привести раскладку к слоям, читаемым в лоб, не меняя парадигму и
внешнее поведение парсеров. Итог: три слоя (`core` / `http` / `sources`) плюс
точка входа (`runner`), с однонаправленными зависимостями.

**Вне скоупа:** любые изменения логики парсинга, CI, `ruff`, широкое покрытие
тестами (пишем только guard-тесты под сам переезд и под развязку).

---

## 2. Целевая структура

```
src/collector/
  __init__.py            public API + side-effect import sources (наполняет registry)
  runner.py              run_parser · _crawl · CrawlResult
  core/                  движок-фреймворк (фундамент)
    __init__.py
    spider/              модель обхода
      __init__.py
      parser.py  request.py  response.py  context.py
    storage/             исходящий контракт + детект изменений
      __init__.py
      sink.py  contracts.py
    registry.py          register_parser / get_parser / registry
  http/                  транспорт
    __init__.py
    client.py  middleware.py
    tls.py               ca_bundle_with_extra_cert
    factory.py           build_http_client (движко-независимый)
    hooks.py             log_request · log_response
  sources/               семейства площадок (было fogsoft/ в корне)
    __init__.py
    fogsoft/
      __init__.py
      base.py            TenderFogsoft (+ RESPONSE_HOOKS)
      platforms.py       конкретные площадки
      parsing/           извлечение данных со страниц
        __init__.py
        tables.py  detail.py  viewstate.py
      inprotect.py       looks_like_challenge · build_cookies · solve_inprotect
      certs/*.pem
```

---

## 3. Правило слоёв (инвариант зависимостей)

Импорты текут в одну сторону:

```
core  ←  http  ←  sources          runner / __init__ — сверху, связывают всё
```

- `core` не импортит `http`/`sources` на рантайме. Единственная ссылка вверх —
  `core/spider/context.py` тянет `HttpClient`, и `core/spider/parser.py` тянет
  `ResponseHook`, оба **только под `TYPE_CHECKING`** (аннотации стрингованы через
  `from __future__ import annotations`). Рантайм-цикла нет.
- `http` знает только `core`. `sources` знает `core` + `http`.
- `runner` и корневой `__init__` — верх пирамиды: импортят из всех слоёв и
  наполняют `registry` side-effect-импортом `sources`.

Проверяется guard-тестом (§8): `collector.runner` не импортит `collector.sources`.

---

## 4. Move-map (файлы и символы)

| Было | Стало | Правки внутри |
|---|---|---|
| `base/parser.py` | `core/spider/parser.py` | + ClassVar-точки расширения (§5.1); импорты соседей на `core.spider.*`, `ChangeStatus` на `core.storage.contracts` |
| `base/request.py` | `core/spider/request.py` | без правок (stdlib/typing) |
| `base/response.py` | `core/spider/response.py` | импорт `Request` на `core.spider.request` |
| `base/context.py` | `core/spider/context.py` | TYPE_CHECKING-импорты на `http.client` / `core.storage.sink` |
| `base/__init__.py` | `core/spider/__init__.py` | ре-экспорт `BaseParser/ParserContext/Request/Response` |
| `sink.py` | `core/storage/sink.py` | импорт `ChangeStatus` на `core.storage.contracts` |
| `contracts.py` | `core/storage/contracts.py` | без правок |
| `registry.py` | `core/registry.py` | импорт `BaseParser` на `core.spider` |
| `runner._ca_bundle_with_extra_cert` | `http/tls.py :: ca_bundle_with_extra_cert` | принимает **абсолютный** путь к cert (§5.3) |
| `runner.build_http_client` | `http/factory.py :: build_http_client` | движко-независимый (§5.4) |
| `http/hooks/logging.py` | `http/hooks.py` | без правок; пакет `http/hooks/` удаляется |
| `http/hooks/inprotect.py` | влит в `sources/fogsoft/inprotect.py` | см. §6 |
| `fogsoft/base.py` | `sources/fogsoft/base.py` | + `RESPONSE_HOOKS` (§5.2); импорты на `core.*` и `sources.fogsoft.parsing.*` |
| `fogsoft/platforms.py` | `sources/fogsoft/platforms.py` | импорты на `sources.fogsoft.base` / `core.registry` |
| `fogsoft/{tables,detail,viewstate}.py` | `sources/fogsoft/parsing/*` | без правок (stdlib/parsel) |
| `fogsoft/inprotect.py` | `sources/fogsoft/inprotect.py` | + хук `solve_inprotect` (§6) |
| `fogsoft/certs/` | `sources/fogsoft/certs/` | без правок |

`runner.py` остаётся в корне и худеет до `run_parser` / `_crawl` / `CrawlResult`;
`import asyncio` поднимается в шапку модуля.

---

## 5. Механизм развязки (движко-независимый `build_http_client`)

Поглощённый спек. Класс парсера сам декларирует свою HTTP-специфику; `factory`
не знает про конкретные движки.

### 5.1. `core/spider/parser.py` — декларативные точки расширения на `BaseParser`

```python
EXTRA_CA_CERT: ClassVar[str | None] = None
SKIP_TLS_VERIFY: ClassVar[bool] = False
RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = ()
```

`ResponseHook` берётся из `collector.http.middleware` под `TYPE_CHECKING`.
`REQUEST_HOOKS` не добавляем — сейчас не нужен (YAGNI).

### 5.2. `sources/fogsoft/base.py` — объявляет специфику у себя

```python
from collector.sources.fogsoft.inprotect import solve_inprotect
RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = (solve_inprotect,)
```

`EXTRA_CA_CERT` / `SKIP_TLS_VERIFY` остаются переопределяемыми в конкретных
парсерах (`MetaInvestParser`, `ArbBitLotParser`) — значения не меняются.

### 5.3. `http/tls.py`

`ca_bundle_with_extra_cert(cert_path: str) -> str` — собирает certifi-бандл +
доп. сертификат сайта, кэширует на диск (`functools.cache`). Принимает
**абсолютный** путь; резолв делает вызывающий (`factory`), а не захардкоженный
`_FOGSOFT_DIR`.

### 5.4. `http/factory.py`

```python
def build_http_client(parser_cls: type[BaseParser]) -> HttpClient:
    middleware = Middleware()
    middleware.request(log_request)
    middleware.response(log_response)
    for hook in parser_cls.RESPONSE_HOOKS:
        middleware.response(hook)

    session_kwargs: dict[str, Any] = {'impersonate': 'chrome'}
    if parser_cls.EXTRA_CA_CERT:
        cert_path = Path(inspect.getfile(parser_cls)).parent / parser_cls.EXTRA_CA_CERT
        session_kwargs['verify'] = ca_bundle_with_extra_cert(str(cert_path))
    elif parser_cls.SKIP_TLS_VERIFY:
        session_kwargs['verify'] = False

    return HttpClient(AsyncSession(**session_kwargs), middleware)
```

Cert-путь резолвится относительно модуля самого класса парсера
(`inspect.getfile`). Для `MetaInvestParser` (в `sources/fogsoft/platforms.py`) с
`EXTRA_CA_CERT = 'certs/…pem'` это даёт `sources/fogsoft/certs/…` — тот же файл,
что и сейчас.

---

## 6. Консолидация `inprotect`

Сейчас concern размазан: solver (`fogsoft/inprotect.py`, чистые функции) + хук
(`http/hooks/inprotect.py`, тонкая обёртка, импортящая solver из http-слоя вниз
в fogsoft). Сливаем в один `sources/fogsoft/inprotect.py`:

- чистые функции `looks_like_challenge`, `build_cookies` — как есть;
- хук `async def solve_inprotect(response, *, session, retry)` рядом; ссылки на
  `build_cookies`/`looks_like_challenge` становятся внутримодульными.

Кросс-слойный импорт `http → fogsoft` исчезает; весь inprotect — в своём движке.

---

## 7. Импорты, которые надо переписать (полный список точек)

- `collector/__init__.py`: `core.spider`, `core.registry`, `core.storage.sink`,
  side-effect `from collector.sources.fogsoft import platforms`; `runner`
  остаётся `collector.runner`.
- `runner.py`: `core.spider` (BaseParser/ParserContext), `http.factory`,
  `core.storage.sink`; убрать импорты fogsoft, `_FOGSOFT_DIR`, `certifi`/
  `tempfile`/`functools` (уехали в `tls.py`); `import asyncio` в шапку.
- `main.py`: `from collector.contracts import ChangeStatus` →
  `from collector.core.storage.contracts import ChangeStatus` (прочее — через
  фасад `collector`).
- Внутрипакетные ссылки по move-map §4.
- `sources/fogsoft/certs/*.pem`: снять устаревший комментарий про `cli.py`
  (косметика, по желанию).

---

## 8. Тестовый тулинг и guard-тесты

Тестов в проекте нет — переезд большой и механический, поэтому дешёвые
guard'ы обязательны.

- `pyproject.toml`: `[dependency-groups] dev = ["pytest", "pytest-asyncio"]`;
  `[tool.pytest.ini_options]`: `pythonpath = ["src"]`, `asyncio_mode = "auto"`,
  `testpaths = ["tests"]`. Команда: `uv run pytest`.

| Тест | Что проверяет |
|---|---|
| `tests/unit/test_public_api.py` | `import collector` работает; `registry()` наполнен (все ожидаемые ключи площадок присутствуют); фасадные символы (`get_parser`, `run_parser`, `LotSink`, …) импортируются |
| `tests/unit/test_layering.py` | `collector.runner` не импортит `collector.sources` (через `inspect.getsource`/AST); `core.*` не импортит `http`/`sources` на рантайме |
| `tests/unit/test_base_hooks.py` | `BaseParser.RESPONSE_HOOKS == ()`; дефолты `EXTRA_CA_CERT`/`SKIP_TLS_VERIFY`; `TenderFogsoft.RESPONSE_HOOKS == (solve_inprotect,)` |
| `tests/unit/http/test_tls.py` | `ca_bundle_with_extra_cert` на временном cert-файле: результат содержит certifi-бандл + доп. сертификат; кэширование (тот же путь → тот же файл). Без сети. |
| `tests/integration/test_factory.py` | у fogsoft-парсера в response-хуках есть `solve_inprotect`, у «голого» `BaseParser`-наследника — нет; `verify=False` при `SKIP_TLS_VERIFY`; резолв `EXTRA_CA_CERT` относительно модуля парсера |

Ни один тест не ходит в сеть.

---

## 9. Порядок реализации (безопасная последовательность)

1. Создать слои и перенести файлы (`git mv`), сохранив содержимое; добавить
   `__init__.py` в новые пакеты. Пока без правок логики.
2. Переписать импорты по §4/§7, пока код не импортируется чисто
   (`uv run python -c "import collector"`).
3. Расщепить `runner` → `http/tls.py` + `http/factory.py`; ввести `RESPONSE_HOOKS`
   и движко-независимый `build_http_client` (§5).
4. Слить `inprotect` (§6), удалить `http/hooks/` пакет.
5. Поднять тестовый тулинг и написать guard-тесты (§8); `uv run pytest` — зелёный.
6. Sanity: `uv run python main.py --list` показывает все площадки.

Каждый шаг — маленький и проверяемый; после 2 и после 5 код должен
импортироваться/тесты проходить.

---

## 10. Definition of Done

- Дерево соответствует §2; корень содержит только `__init__.py`, `runner.py` и
  пакеты `core/`, `http/`, `sources/`.
- `runner.py` — только `run_parser` / `_crawl` / `CrawlResult`, `import asyncio`
  в шапке, без импортов из `sources` и без `_FOGSOFT_DIR`.
- `build_http_client` в `http/factory.py`, движко-независимый (через
  `RESPONSE_HOOKS` + `inspect.getfile`); TLS-утилита в `http/tls.py`.
- Весь inprotect-concern в `sources/fogsoft/inprotect.py`; пакета `http/hooks/`
  нет.
- `uv run pytest` — зелёный; guard-тесты §8 проходят; сети нет.
- Внешнее поведение парсеров не изменилось (cert-путь `MetaInvestParser`
  резолвится в тот же файл; порядок response-хуков прежний: `solve_inprotect`
  раньше, `log_response` последним).

---

## 11. Найденное к следующим заходам (НЕ трогаем сейчас)

- Широкое покрытие тестами «чистой» логики (`contracts`, `viewstate`, `detail`,
  `inprotect`, `registry`, `middleware`) и оркестрации краулера.
- `ruff` + CI.
- Возможный перенос `CrawlResult` в `core/storage` и выделение entrypoint —
  если появится второй способ запуска помимо синхронного моста.
