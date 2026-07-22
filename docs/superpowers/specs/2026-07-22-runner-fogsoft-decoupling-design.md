# Дизайн: развязка `runner` ↔ `fogsoft` + микро-правки

**Дата:** 2026-07-22
**Статус:** утверждён к реализации
**Порядок работы:** архитектура/код — первым; тесты пишем **сразу под каждый
шаг** (плотно чередуя), а не наоборот.

---

## 1. Цель и контекст

`collector` — асинхронный движок парсеров торговых площадок, отвязанный от
Django. Расслоение в проекте выдержано почти везде: ядро знает про хранилище
только через `LotSink` (Protocol), `registry` не знает про ORM, парсеры не знают
про транспорт.

**Единственная кривая граница:** `runner.build_http_client(parser_cls)`
([src/collector/runner.py](../../../src/collector/runner.py)) — «общий» раннер
жёстко знает про конкретный движок `fogsoft`:

- `if issubclass(parser_cls, TenderFogsoft): middleware.response(solve_inprotect)`
  — проверка базового класса конкретного движка;
- `EXTRA_CA_CERT` резолвится относительно захардкоженного `_FOGSOFT_DIR`;
- импорты `from collector.fogsoft.base import TenderFogsoft` и `solve_inprotect`
  в общем раннере.

**Цель захода:** выпрямить эту границу — сделать `build_http_client`
движко-независимым, чтобы класс парсера сам декларировал свою HTTP-специфику.
Плюс две микро-правки, вскрытые по ходу.

**Вне скоупа:** любые другие рефакторинги, CI, широкое покрытие тестами
(тесты пишем только под изменённый код).

---

## 2. Дизайн

### 2.1. `BaseParser` — декларативные точки расширения

Файл `src/collector/base/parser.py`:

- Перенести из `TenderFogsoft` в `BaseParser` классовые атрибуты TLS (это общие
  понятия, не fogsoft-специфика):
  - `EXTRA_CA_CERT: ClassVar[str | None] = None`
  - `SKIP_TLS_VERIFY: ClassVar[bool] = False`
- Добавить точку расширения для response-хуков движка:
  - `RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = ()`

`REQUEST_HOOKS` намеренно **не** добавляем — сейчас не нужен (YAGNI).

Выбор «декларативный кортеж `RESPONSE_HOOKS`» против «classmethod
`configure_middleware`»: кортеж проще, это чистые данные (легко тестировать) и
он в стиле кода (проект активно использует `ClassVar` и `__init_subclass__`).

### 2.2. `TenderFogsoft` — объявляет свою специфику у себя

Файл `src/collector/fogsoft/base.py`:

- `from collector.http.hooks.inprotect import solve_inprotect`
- `RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = (solve_inprotect,)`

`EXTRA_CA_CERT` / `SKIP_TLS_VERIFY` остаются переопределяемыми в конкретных
парсерах (`MetaInvestParser`, `ArbBitLotParser`) — как сейчас, значения не
меняются.

### 2.3. Новый модуль `collector/http/tls.py`

Перенести из `runner.py` функцию `_ca_bundle_with_extra_cert` →
`ca_bundle_with_extra_cert(cert_path: str) -> str` (общая TLS-утилита: собирает
certifi-бандл + доп. сертификат сайта, кэширует на диск через
`functools.cache`). Место ей не в раннере.

Сигнатура меняется: принимает **абсолютный** путь к cert-файлу (резолв делает
вызывающий), а не relative-путь + захардкоженный `_FOGSOFT_DIR`.

### 2.4. `runner.build_http_client` — движко-независимый

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

- Уходят импорты `from collector.fogsoft.base import TenderFogsoft`,
  `from collector.http.hooks.inprotect import solve_inprotect`, константа
  `_FOGSOFT_DIR`.
- Cert-путь резолвится относительно **модуля самого класса парсера**
  (`inspect.getfile(parser_cls)`), а не папки fogsoft. Для `MetaInvestParser`
  (объявлен в `fogsoft/platforms.py`) это даёт `fogsoft/certs/…` — тот же путь,
  что и сейчас.

### 2.5. Инварианты, которые НЕ должны сломаться

- **Порядок response-хуков.** `response()` делает `appendleft` (LIFO): сначала
  регистрируется `log_response`, затем `solve_inprotect` → `solve_inprotect`
  выполняется первым, `log_response` — последним. Как сейчас.
- **Отсутствие циклов импорта.** `fogsoft/base → http/hooks/inprotect →
  fogsoft/inprotect → stdlib`. Обратно на `fogsoft/base` цепочка не замыкается.
- **Внешнее поведение парсеров** (что и как собирается) не меняется.

---

## 3. Микро-правки (в этом же заходе)

- `runner.py`: поднять `import asyncio` из тела `run_parser` в шапку модуля.
  (Это **не** дубль — импорт единственный; правка чисто стилистическая.)
- `fogsoft/tables.py`: нейтрализовать привязанные к одной площадке ключи логов —
  `centerr.bad_price` → `fogsoft.tables.bad_price`,
  `centerr.bad_max_pages` → `fogsoft.tables.bad_max_pages`
  (функции общие для всех площадок, префикс `centerr` вводит в заблуждение).

---

## 4. Тестовый тулинг (минимально, чтобы было чем гонять тесты)

- `pyproject.toml`: `[dependency-groups] dev = ["pytest", "pytest-asyncio"]`;
  `[tool.pytest.ini_options]`: `pythonpath = ["src"]`, `asyncio_mode = "auto"`,
  `testpaths = ["tests"]`.
- `ruff` и CI — вне скоупа этого захода.
- Команда: `uv run pytest`.

---

## 5. Тесты — сразу под изменённый код

Пишем **только** то, что покрывает затронутое (не всё ядро — это следующие
заходы):

| Тест | Что проверяет |
|---|---|
| `tests/unit/test_base_hooks.py` | `BaseParser.RESPONSE_HOOKS == ()`; `EXTRA_CA_CERT`/`SKIP_TLS_VERIFY` дефолты; `TenderFogsoft.RESPONSE_HOOKS == (solve_inprotect,)` |
| `tests/unit/http/test_tls.py` | `ca_bundle_with_extra_cert` на временном cert-файле: результат содержит и certifi-бандл, и доп. сертификат; кэширование (одинаковый путь → тот же файл). Без сети. |
| `tests/integration/test_build_http_client.py` | для fogsoft-парсера в `RESPONSE_HOOKS`-хуках присутствует `solve_inprotect`; для «голого» наследника `BaseParser` — нет; `verify=False` при `SKIP_TLS_VERIFY`; резолв `EXTRA_CA_CERT` относительно модуля парсера |
| `tests/unit/test_runner_decoupling.py` | статически: модуль `collector.runner` не импортирует `collector.fogsoft` (проверка через `inspect.getsource`/AST или `sys.modules` после изолированного импорта) |
| `tests/unit/fogsoft/test_tables_logging.py` | `parse_price`/`read_max_pages` на «мусорных» входах возвращают `None` и логируют под новым нейтральным ключом (через `caplog`) |

Ни один тест не ходит в сеть.

---

## 6. Definition of Done

- `runner.py` не содержит импортов из `collector.fogsoft` и константы
  `_FOGSOFT_DIR`; `build_http_client` работает через `RESPONSE_HOOKS` и
  `inspect.getfile`.
- `import asyncio` в шапке `runner.py`; ключи логов в `tables.py`
  нейтрализованы.
- `uv run pytest` — зелёный; тесты из §5 проходят; сети нет.
- Поведение парсеров не изменилось (cert-путь `MetaInvestParser` резолвится в
  тот же файл; порядок хуков прежний).

---

## 7. Найденное к следующим заходам (НЕ трогаем сейчас)

- Широкое покрытие тестами «чистой» логики (`contracts`, `viewstate`, `detail`,
  `inprotect`, `registry`, `middleware`) и оркестрации краулера — отдельный
  заход (тест-фундамент).
- `ruff` + CI.
