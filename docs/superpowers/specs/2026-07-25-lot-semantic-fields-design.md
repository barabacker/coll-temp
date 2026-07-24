# Дизайн: каноничные торговые поля Lot (устранение семантического дрейфа)

**Дата:** 2026-07-25
**Статус:** утверждён к реализации
**Контекст:** §7 спека `2026-07-22-lot-pydantic-model-design.md`. Плоская модель
`Lot` сохраняется; правим только смысл торговых полей.

---

## 1. Проблема

`trade_title` означает разное по движкам (проверено на данных):

| движок | `trade_title` сейчас | на самом деле |
|---|---|---|
| fogsoft | «Багаутдинова Рузиля Вазировна» | **должник** |
| kendo | «10777–ОТПП (Открытые торги…)» | номер + описание типа |
| btorg | «12850-ОАОФ» | номер торгов |
| ruson | «68240-ОАОФ» | номер торгов |

Должник нигде не выделен; организатор у ruson берётся из detail и часто `None`.

## 2. Решение

В модели `Lot`:
- **убрать** `trade_title` (неоднозначный);
- **добавить** `trade_number: str | None` (номер/код торгов) и
  `debtor: str | None` (должник).

`FINGERPRINT_FIELDS` (`core/storage/contracts.py`): заменить `trade_title` →
`trade_number` (fingerprint считается по сырому dict листинга в `fogsoft.parse`;
`trade_number` там будет присутствовать).

## 3. Пер-движковый маппинг источников (проверено по фикстурам)

| поле | fogsoft | btorg | kendo | ruson |
|---|---|---|---|---|
| `trade_number` | `trade_id` (цифры, напр. «0099382») | `td[0]` (код) | код карточки (`trade['trade_number']`) | код (`trade['trade_number']`) |
| `debtor` | `td[2]` | `td[1]` | регуляркой `должник[аи]?\s+(.+)$` из заголовка карточки | колонка «Должник» листинга (по заголовку) |
| `organizer` | `td[6]` (как есть) | `td[2]` bold (как есть) | секция «Организатор торгов» (как есть) | колонка «Организатор» листинга (по заголовку) |

### 3.1. fogsoft (`parsing/tables.py :: parse_table`)
- `'debtor': clean(tr.xpath('string(./td[2])').get())` (было `trade_title`);
- `'trade_number': trade_id`; убрать ключ `trade_title`.

### 3.2. btorg (`parsing/listing.py` + `parsing/lots.py`)
- listing: добавить `'debtor': clean(tds[1].xpath('string(.)').get())`;
- lots: `'trade_number': trade.get('trade_number')`, `'debtor': trade.get('debtor')`;
  убрать `trade_title`.

### 3.3. kendo (`parsing/listing.py` — только для внутреннего trade-dict — не
трогаем; `base.py`)
- `base.parse_detail`/`extract_lots`: `trade_ctx['trade_number'] = trade.get('trade_number')`;
  `trade_ctx['debtor']` = регуляркой `_DEBTOR_RE = re.compile(r'должник[аи]?\s+(.+)$', re.I)`
  из `trade.get('trade_title')`; больше не проставлять `trade_title`.
- `parse_lots` (`parsing/detail.py`): эмитить `trade_number`/`debtor` из `trade`,
  убрать `trade_title`.

### 3.4. ruson (`parsing/listing.py` + `parsing/detail.py`)
- listing: колонки организатора/должника по заголовку. Хелпер:
  ```python
  def _col_by_header(table, header_substr):
      heads = [clean(th.xpath('string(.)').get()) or '' for th in table.xpath('.//tr[th]/th')]
      return next((i for i, h in enumerate(heads) if header_substr in h.lower()), None)
  ```
  На строку — брать `td[idx]` по найденному индексу (в пределах одной таблицы;
  индекс считается один раз на страницу). Если заголовка нет (node_view/lot-листинги
  без `<th>`) — `organizer`/`debtor` = `None` (best-effort; авторитетно из
  листинга не выводится).
- detail `parse_lots`: `trade_number` из `trade`; `organizer`/`debtor` из `trade`
  (листинг), НЕ из detail; убрать `trade_title` и старый detail-`organizer`.

## 4. Инварианты
- Плоская `Lot` не меняет форму (только состав полей: −1, +2).
- `extra`-блоб не трогаем (полный маппинг лейблов — §7-осталось, YAGNI сейчас).
- `parse_lots`/`parse_table` возвращают dict'ы; конвертация в `Lot` на границе
  (не меняется).
- Даты/`is_active`/`source`/`extra` — как в предыдущем заходе.

## 5. Тесты
- `tests/unit/test_lot.py`: обновить `FULL_ITEM`/`MINIMAL_ITEM` — `trade_title`→
  `trade_number`, добавить `debtor`; ассерты `lot.trade_number`, `lot.debtor`.
- Юнит-тесты парсеров (btorg/ruson/kendo `parse_lots`, при наличии): ассерты на
  `trade_number`/`debtor` вместо `trade_title`.
- Интеграционные краул-тесты: `first.trade_number` / `first.debtor` (где было
  `first.trade_title` — его больше нет).
- Новый `tests/unit/test_semantic_fields.py`: на фикстурах по движку —
  `parse_listing`/`parse_lots` дают ожидаемые `trade_number` и `debtor`
  (kendo debtor «Баранов Виталий Витальевич»; btorg debtor «Летовальцева…»;
  ruson organizer «Чахоян…», debtor «Ионов…»; fogsoft — синтетическая строка,
  т.к. фикстур нет).
- `uv run pytest` — зелёный.

## 6. Definition of Done
- `Lot`: без `trade_title`, с `trade_number`/`debtor`; `FINGERPRINT_FIELDS`
  использует `trade_number`.
- Все 4 движка эмитят `trade_number`+`debtor`, не эмитят `trade_title`.
- Живой smoke по одному сайту на движок: `trade_number` и `debtor` заполнены
  (fogsoft — если домен доступен; иначе покрыт юнит-тестом).
- `uv run pytest` зелёный.

## 7. Вне скоупа
- Полный маппинг `extra` в типизированные под-поля.
- Разнесение trade↔lots на сущности.
- Нормализация `trade_type` fogsoft (полный текст) → код.
