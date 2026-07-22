# Дизайн: движок btorg/edoc-ETP (`sources/btorg`)

**Дата:** 2026-07-22
**Статус:** утверждён к реализации
**Контекст:** второй новый движок из `PLATFORM.xlsx` (после Kendo-ETP).
Зеркалит отработанный Kendo-паттерн (листинг = торги → dive → per-lot items),
с btorg-спецификой. Остальные (`rus-on`, `individual`) — отдельные заходы.

---

## 1. Цель

Движок-семейство **btorg/edoc-ETP** — 6 площадок с единым шаблоном
`/etp/trade/list.html`. Модель лот-центричная (item-ключи как у fogsoft/kendo,
`LotSink`/`lot_fingerprint` без изменений).

| parser_key | domain |
|---|---|
| `atctrade` | atctrade.ru |
| `ausib` | ausib.ru |
| `etp_profit` | etp-profit.ru |
| `aukcioncenter` | aukcioncenter.ru |
| `regtorg` | regtorg.com |
| `ptp_center` | ptp-center.ru |

**Вне скоупа:** приём/подведение даты с `general.html` (доп. фетч; v1 берёт
дату листинга), `rus-on`/`individual`.

---

## 2. Разведка (подтверждено на `atctrade.ru`, curl_cffi, без логина)

- **Листинг**: `GET /etp/trade/list.html?page=N`. HTML `table.data` (единственная
  с этим классом), **строка = торги**, 5 колонок:
  `td0`=номер+тип (`12850-ОАОФ`), `td1`=должник, `td2`=организатор (в
  `div[font-weight:bold]`) + описание предмета, `td3`=статус, `td4`=дата.
  Пагинация: ссылки `list.html?page=2..N`.
- **Detail-id**: строка `<tr onclick="…window.location='/trade/view/purchase/general.html?id=105448698'…">`
  → `purchase_id` регуляркой `id=(\d+)` из `onclick` (JS не исполняем).
- **Лоты** (там, где цены): `GET /etp/trade/inner-view-lots.html?perspective=inline&id={purchase_id}`.
  Ответ — HTML (**Windows-1251**), таблицы `table.data` с `id="lotNumberN"` (по
  одной на лот), строки label→value:
  «Предмет торгов», «Cведения об имуществе…», «Классификатор имущества»,
  **«Начальная цена продажи имущества»** = `280 000,00 руб, НДС не облагается`,
  «Величина повышения начальной цены», «Размер задатка», «Статус торгов»,
  «Другие документы».
- Ни ViewState, ни анти-бота. `curl_cffi` (chrome) читает всё; `r.text` уже
  декодирует 1251 → parsel получает Unicode.

---

## 3. Дизайн

### 3.1. Раскладка

```
collector/sources/btorg/
  __init__.py
  base.py         TenderBtorg(BaseParser)
  platforms.py    6 площадок (@register_parser)
  parsing/
    __init__.py
    listing.py    parse_listing (table.data → торги), find_next_page, read_max_pages, parse_price
    lots.py       parse_lots (inner-view-lots → per-lot items)
```

### 3.2. `TenderBtorg` (base.py)

- `DOMAIN`, `LISTING_PATH='etp/trade/list.html'`; `BASE_URL`/`start_urls` в
  `__init_subclass__`. `RESPONSE_HOOKS=()`.
- `parse(response)`:
  - `trades = parse_listing(sel, self.name)` (строки `table.data`);
  - для каждой — dive на `LOTS_PATH?perspective=inline&id={purchase_id}`:
    `yield self.request(urljoin(base, lots_url), callback=self.parse_lots_page, metadata={'trade': trade})`;
  - пагинация: `find_next_page(sel, page)` + `read_max_pages`.
- `parse_lots_page(response)`: `lots = parse_lots(sel, trade)`; `yield` каждый лот.

`LOTS_PATH = '/etp/trade/inner-view-lots.html'`. Запрос лотов — с заголовком
`X-Requested-With: XMLHttpRequest` (через `self.request(..., headers=...)`), на
случай если эндпоинт требует XHR-контекст (проверить; если не нужен — убрать).

### 3.3. `parsing/listing.py`

- `parse_listing(sel, source) -> list[trade dict]` по `//table[@class="data"]//tr[@onclick]`:
  `trade_number` (td0), `trade_id` (цифры номера), `purchase_id` (из `onclick`),
  `debtor` (td1), `organizer` (td2 `div.bold`), `object_desc` (td2 остальное),
  `status` (td3), `list_date` (td4), `lots_url`
  (`/etp/trade/inner-view-lots.html?perspective=inline&id={purchase_id}`),
  `_source`.
- `find_next_page(sel, page)` — из `a[href*="list.html?page="]`, минимальный
  номер `> page`.
- `read_max_pages(params)` — дубль helper'а (движки независимы).
- `parse_price(value)` — извлекает ведущее число из `280 000,00 руб …`
  (comma-decimal): `re.match(r'[\d\s .,]+', value)` → чистка (`\xa0`/пробелы
  убрать, `,`→`.`) → `float`; иначе `None` + warning `btorg.bad_price`.

### 3.4. `parsing/lots.py` и маппинг item (ключи как у fogsoft/kendo)

`parse_lots(sel, trade) -> list[item]` по `//table[contains(@id,"lotNumber")]`:

| ключ item | источник |
|---|---|
| `lot_id` | `f'{trade_id}_{lot_num}'` |
| `trade_id` | из `trade` |
| `lot_num` | индекс из `id="lotNumberN"` (или порядковый) |
| `trade_title` | `trade['trade_number']` |
| `lot_url` | `trade['lots_url']` (общий на торги; per-lot URL нет) |
| `description` | «Предмет торгов» + «Cведения об имуществе…» |
| `price` | `parse_price(«Начальная цена продажи имущества»)` → float; `price_raw` — сырое |
| `status` | «Статус торгов» (или `trade['status']`) |
| `organizer` | `trade['organizer']` |
| `bidding_date` | `trade['list_date']` |
| `event_date` | `None` (см. §1 вне скоупа) |
| `trade_type` | суффикс номера после `-` (`ОАОФ`) |
| `_source` | имя парсера |
| `detail` | dict всех label→value лота (задаток, шаг, классификатор, …) |
| `attachments` | ссылки из «Другие документы»/«Приложенные файлы» (если есть) |

`FINGERPRINT_FIELDS` = `status, price, bidding_date, event_date, trade_title` —
`status`/`price`/`trade_title` наполнены; `bidding_date` = дата листинга;
`event_date` None (стабильно). Отпечаток считается штатно.

Поле-экстрактор: `lot.xpath('.//tr[td[1][contains(normalize-space(.),"LABEL")]]/td[2]')` → `string()`.

### 3.5. Регистрация

6 классов `@register_parser` в `platforms.py`; фасад `collector/__init__.py` —
side-effect импорт `from collector.sources.btorg import platforms`.

---

## 4. Инварианты

- fogsoft/kendo/core/http не трогаем; btorg — независимый сосед.
- `LotSink`/`contracts` без изменений (item fogsoft-совместим).
- `EXPECTED_KEYS` в `test_public_api.py`: +6 → 26.
- Layering: `sources/btorg` зависит только от `core` (+ `http` типы) — под
  guard-тест `test_layering` попадает.

---

## 5. Тесты (офлайн, без сети)

Фикстуры (сняты curl_cffi, UTF-8): `tests/fixtures/btorg/atctrade_listing.html`,
`atctrade_lots.html`.

| Тест | Что проверяет |
|---|---|
| `tests/unit/btorg/test_listing.py` | `parse_listing`: N торгов; первая — `trade_number='12850-ОАОФ'`, `trade_id='12850'`, `purchase_id='105448698'`, `status`, `lots_url` содержит id; `parse_price('280 000,00 руб …')==280000.0`, `parse_price(None)/мусор→None`; `find_next_page` |
| `tests/unit/btorg/test_lots.py` | `parse_lots` на fixture: ≥1 лот; первый — `lot_id='12850_1'`, `price==280000.0`, `status`, `description` непустое, `trade_title='12850-ОАОФ'` |
| `tests/unit/btorg/test_registration.py` | 6 kendo-ключей в registry; `BASE_URL` вывод; `RESPONSE_HOOKS==()` |
| `tests/integration/test_btorg_crawl.py` | краул через фейковый `HttpClient` (листинг+lots из fixture): листинг→dive→per-lot items; ключи fogsoft-совместимы; `max_pages` |
| `tests/unit/test_public_api.py` | `EXPECTED_KEYS` = 26 |

Ни один тест не ходит в сеть.

---

## 6. Definition of Done

- `sources/btorg/{base,platforms,parsing/listing,parsing/lots}.py`; 6 площадок в
  registry; фасад импортит btorg.
- Item-ключи fogsoft-совместимы; `lot_fingerprint` считается.
- `EXPECTED_KEYS`=26; `uv run pytest` зелёный; сети в тестах нет.
- **Живая проверка всех 6 площадок** end-to-end (`main.py <key> 1`): собирают
  лоты с непустыми `price`/`status`/`lot_id`.
- fogsoft/kendo/core/http не изменены.

---

## 7. Квирки / оговорки

- **Windows-1251** на lots-эндпоинте — `curl_cffi.r.text` декодирует сам;
  проверить, что кириллица не бьётся (fixture в UTF-8).
- **id из `onclick`** — регуляркой; если у части площадок формат onclick иной —
  параметризовать (проверяется живой проверкой 6 сайтов).
- **XHR-заголовок** на lots-эндпоинт — проверить, нужен ли; убрать, если нет.
- **Даты приём/подведение** — на `general.html` (доп. фетч на торги). v1 берёт
  дату листинга в `bidding_date`; полноценные даты — следующий заход, если нужно.
- Верификация единого шаблона по всем 6 — на этапе живой проверки (как выяснилось
  на Kendo, площадки одной группы могут иметь варианты разметки).
