# Дизайн: движок Kendo-ETP (`sources/kendo`)

**Дата:** 2026-07-22
**Статус:** утверждён к реализации
**Контекст декомпозиции:** это первый из новых движков по `PLATFORM.xlsx`.
Остальные (`btorg/edoc-ETP`, `rus-on`, `individual`) — отдельные заходы
(свой спек→план на каждый). `iTender/Fogsoft` уже реализован.

---

## 1. Цель

Добавить движок-семейство **Kendo-ETP** — асинхронный парсер площадок торгов по
банкротству на платформе с Kendo UI grid. Пять площадок с единым шаблоном:

| parser_key | domain | start_url |
|---|---|---|
| `trade_alliance` | trade-alliance.ru | https://trade-alliance.ru/lots |
| `seltim` | bankrupt.seltim.ru | https://bankrupt.seltim.ru/lots |
| `electro_torgi` | bankrotstvo.electro-torgi.ru | https://bankrotstvo.electro-torgi.ru/lots |
| `torgi82` | lot.torgi82.ru | https://lot.torgi82.ru/lots |
| `vetp` | банкрот.вэтп.рф (IDN) | https://банкрот.вэтп.рф/lots |

Модель — **лот-центричная** (как fogsoft): одна запись = один лот. Итемы имеют
те же ключи, что у fogsoft, чтобы `LotSink` и `lot_fingerprint` работали без
изменений.

**Вне скоупа:** trade-level skip-оптимизация (см. §7), price-schedule для
публичного предложения, прочие движки, полная верификация 4 площадок сверх
проверки единого шаблона.

---

## 2. Разведка (подтверждено на `trade-alliance.ru`, сырой HTML)

- Стек: jQuery + Kendo UI 2017.3 + Materialize. **Листинг и detail —
  server-rendered HTML**, данные в исходном ответе. **JS для парсинга не нужен**
  (curl_cffi + parsel достаточно). Ни ViewState, ни anti-bot (inprotect) — нет.
- **Листинг:** `GET /lots?page=N`. Пагинация — обычный
  `<ul class="pagination">` со ссылками `?page=2..N`. Карточка листинга =
  **одни торги** (процедура), внутри — несколько лотов.
- **Detail:** `GET /{type_code}/{trade_id}` (напр. `/oaof/10775`). Одна
  страница, вкладки — якоря (`#main-info` / `#lots` / `#documents`), весь
  контент в одном ответе.
- **Лоты в detail:** `div#lots > a.block-lot`, у каждого:
  - ссылка на лот `a.blue-text[href]` → `/oaof/10775/lots/3090` (внутр. id
    лота) + описание;
  - «Номер лота:» → `span.normal.black-text` (напр. `5`);
  - «Статус лота:» → `span.competition-status-round.lot-status-N` + текст
    («Идет прием заявок»);
  - **цена** → `span.fs36` (напр. `6 721 200.00`, копейки в `span.kopeyki`).
- **Detail #main-info:** label→value пары (организатор, арб. управляющий,
  должник ИНН/СНИЛС, суд, № дела, статус торгов, даты приёма заявок / ценовых
  предложений / подведения, задаток, ЕФРСБ id).
- **Тип→код** для detail-URL: `10775–ОАОФ` → `/oaof/10775` (буквенный суффикс
  номера в нижнем регистре = code). Коды берём из detail-ссылок листинга (не
  вычисляем сами) — надёжнее.

---

## 3. Дизайн

### 3.1. Раскладка

```
collector/sources/kendo/
  __init__.py
  base.py         TenderKendo(BaseParser)
  platforms.py    5 площадок (@register_parser)
  parsing/
    __init__.py
    listing.py    parse_listing(sel) -> list[trade dict]; find_next_page(sel, page)
    detail.py     parse_lots(sel, trade) -> list[item]; parse_main_info(sel); parse_documents(sel)
```

Зеркалит `sources/fogsoft/` (base + platforms + parsing/). Никакого `inprotect`,
`viewstate`, `certs` — не требуются. `sources/__init__.py` и фасад не меняем в
структуре; регистрация площадок — side-effect импортом (см. §3.6).

### 3.2. `TenderKendo` (base.py)

Классовые атрибуты:
- `DOMAIN: ClassVar[str]` — корень сайта (напр. `https://trade-alliance.ru`).
- `LISTING_PATH: ClassVar[str] = 'lots'`; `BASE_URL`/`start_urls` выводятся в
  `__init_subclass__` (как у `TenderFogsoft`).
- `RESPONSE_HOOKS = ()` (нет анти-бота). `EXTRA_CA_CERT`/`SKIP_TLS_VERIFY` —
  дефолты из `BaseParser`, переопределяются в конкретной площадке при TLS-квирке.

Поток:
- `parse(response)` (страница листинга):
  - `trades = parse_listing(sel)` — карточки торгов;
  - лог `page | items | total`;
  - для каждой торговой процедуры — **всегда** dive:
    `yield self.request(urljoin(base, trade['detail_url']), callback=self.parse_detail, metadata={'trade': trade})`;
  - пагинация: `next_page = find_next_page(sel, page)`; при
    `next_page and (max_pages is None or page < max_pages)` —
    `yield self.request(f'{BASE_URL}?page={page+1}', metadata={'page': page+1})`.
    `max_pages` через `read_max_pages(self.ctx.params)` — маленький helper
    **дублируем** в `kendo/parsing/listing.py` (kendo **не** импортит fogsoft;
    движки независимы). Вынос общего `read_max_pages` в `core` — возможный
    отдельный cleanup, вне скоупа.
- `parse_detail(response)`:
  - `lots = parse_lots(sel, trade)` — по одному item на `a.block-lot`;
  - `main = parse_main_info(sel)`, `docs = parse_documents(sel)`;
  - для каждого лота: собрать item (§3.4), проставить `item['detail'] = main`,
    `item['attachments'] = docs`; `yield item`.

`REQUEST_HOOKS`/`price_schedule` не добавляем (YAGNI).

### 3.3. `parsing/listing.py`

- `parse_listing(selector) -> list[dict]` — по карточке торгов извлекает:
  `trade_id` (число из «Номер торгов: 10775–ОАОФ»), `trade_type_label`
  (расшифровка типа), `detail_url` (ссылка `/{code}/{id}` из карточки),
  `status` (статус торгов), `debtor`, `organizer`, `bidding_date`,
  `event_date`, `total_sum_raw`, `lot_count`.
  Точные xpath финализируются по сохранённой fixture листинга (структуру полей
  разведка подтвердила; конкретные классы карточки снимаем с fixture).
- `find_next_page(selector, current_page) -> int | None` — из
  `ul.pagination a[href*="page="]` берёт минимальный номер `> current_page`
  (или `None`, если следующей нет).

### 3.4. `parsing/detail.py` и маппинг item (ключи как у fogsoft)

`parse_lots(selector, trade) -> list[dict]` — по `div#lots a.block-lot`:

| ключ item | источник (Kendo) |
|---|---|
| `lot_id` | `f'{trade_id}_{lot_num}'` |
| `trade_id` | из `trade` (листинг) |
| `lot_num` | «Номер лота:» `span.normal.black-text` |
| `lot_internal_id` | из href `/…/lots/{id}` |
| `trade_title` | заголовок торгов (из `trade`/detail) |
| `lot_url` | `a.blue-text/@href` (абсолютизируем) |
| `description` | текст `a.blue-text` |
| `price` | `parse_price(span.fs36)` → float; `price_raw` — сырой текст |
| `status` | «Статус лота:» текст рядом с `span.lot-status-N` |
| `organizer` | из `main_info` |
| `bidding_date` | из `trade`/`main_info` (окончание приёма заявок) |
| `event_date` | из `trade`/`main_info` (подведение результатов) |
| `trade_type` | `trade_type_label` из листинга |
| `_source` | имя парсера |

- `parse_price(text)` — как в fogsoft (пробелы/`\xa0` убрать, запятая→точка,
  `float`; иначе `None` + warning с ключом `kendo.detail.bad_price`).
- `parse_main_info(selector) -> dict[str, str]` — label→value пары секции
  `#main-info` (аналог `parse_detail_sections`, но плоский dict — тут одна
  секция «Информация о торгах» + блоки организатора/должника; точные селекторы
  по fixture).
- `parse_documents(selector) -> list[dict]` — из `#documents`: `{name, url}`
  (аналог `parse_attachments`).

`FINGERPRINT_FIELDS` = `status, price, bidding_date, event_date, trade_title` —
все присутствуют в item, отпечаток per-lot считается штатно.

### 3.5. Даты — семантика

fogsoft-семантику `bidding_date`/`event_date` в этом заходе воспроизводим так:
`bidding_date` = окончание приёма заявок, `event_date` = подведение результатов
торгов. Помечено как **предположение** — сверить с тем, как downstream (Django
`Lot`) трактует эти поля; при расхождении — поправить маппинг (это только
`detail.py`, без изменения контракта).

### 3.6. Регистрация площадок (platforms.py)

Пять классов `@register_parser(key)` с `DOMAIN`. Плюс в фасаде
`collector/__init__.py` — side-effect импорт нового модуля площадок:
`from collector.sources.kendo import platforms as _kendo_platforms  # noqa`.
IDN-домен `банкрот.вэтп.рф`: `DOMAIN` храним в Unicode; curl_cffi/`urljoin`
кодируют в punycode сами (проверить при верификации площадки).

---

## 4. Инварианты / что не ломаем

- **fogsoft не трогаем** — новый движок независим (соседний пакет).
- **`LotSink`/`contracts` не меняем** — item-ключи fogsoft-совместимы.
- **Registry safety-net.** `tests/unit/test_public_api.py::EXPECTED_KEYS`
  вырастет на 5 kendo-ключей (с 15 до 20) — обновляется в этом заходе.
- **Слои.** `sources/kendo` зависит только от `core` (+ `http` типы) — под
  guard-тест `test_layering` попадает автоматически.

---

## 5. Тесты (офлайн, без сети)

Фикстуры — **сырой HTML живых страниц** (снимается через браузер/VPN в ходе
реализации; см. §7): `tests/fixtures/kendo/listing_page1.html`,
`tests/fixtures/kendo/detail_oaof.html`.

| Тест | Что проверяет |
|---|---|
| `tests/unit/kendo/test_listing.py` | `parse_listing` на fixture: N карточек, у первой корректные `trade_id`/`detail_url`/`status`/даты; `find_next_page` даёт 2 на 1-й, `None` на последней |
| `tests/unit/kendo/test_detail.py` | `parse_lots` на fixture: 2 лота; у первого `lot_id='10775_5'`, `price==6721200.0`, `status`, `lot_url`, `description`; `parse_main_info`/`parse_documents` непустые |
| `tests/integration/test_kendo_crawl.py` | краулинг через фейковый `HttpClient` (отдаёт fixture-HTML по URL): листинг→dive→per-lot items; item-ключи fogsoft-совместимы; `max_pages` ограничивает |
| `tests/unit/test_public_api.py` | обновлённый `EXPECTED_KEYS` (20 ключей) |

Ни один тест не ходит в сеть. Прогон `uv run pytest` — зелёный.

---

## 6. Definition of Done

- `collector/sources/kendo/{base,platforms,parsing/listing,parsing/detail}.py`
  реализованы; 5 площадок в registry; фасад импортит kendo-платформы.
- `parse_listing`/`find_next_page`/`parse_lots`/`parse_main_info`/
  `parse_documents` покрыты офлайн-тестами на fixture.
- Item-ключи совпадают с fogsoft; `lot_fingerprint` считается по ним.
- `EXPECTED_KEYS` = 20; `uv run pytest` зелёный; сети в тестах нет.
- `uv run python main.py --list` показывает 5 kendo-ключей;
  `uv run python main.py trade_alliance 1` (ручная проверка, сеть) собирает
  лоты с непустыми `price`/`status`.
- fogsoft и `core`/`http` не изменены.

---

## 7. Оговорки и следующие заходы

- **Верификация 4 площадок.** Проверял только `trade-alliance.ru`. Перед
  регистрацией — снять по одной fixture с каждой из остальных и убедиться в
  едином шаблоне (селекторы карточки/лота, схема detail-URL, IDN-домен). При
  расхождении — параметризовать селекторы или выделить подкласс.
- **Фикстуры.** Снимаются с живых сайтов (нужен VPN-доступ). Реализатор без
  доступа их не добудет — фикстуры готовит тот, у кого есть браузер/VPN (я в
  ходе реализации, либо пользователь прикладывает HTML).
- **trade-level skip** (не ныряем в неизменившиеся торги) — оптимизация трафика;
  требует хранить отпечаток на уровне торгов (изменения в sink/БД). Отдельный
  заход, если объём запросов станет проблемой.
- **price-schedule** для публичного предложения (ОТПП, снижение цены) — при
  необходимости, отдельно.
- Прочие движки `btorg/edoc-ETP`, `rus-on`, `individual` — свои спеки.
