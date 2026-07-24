# Дизайн: стандартизация item'а через Pydantic-модель `Lot`

**Дата:** 2026-07-22
**Статус:** утверждён к реализации
**Скоуп:** первый проход — типизированная модель + нормализация значений. НЕ
БД-схема, НЕ разнесение trade/lots на сущности, НЕ починка семантического дрейфа
полей между движками (следующие заходы).

---

## 1. Проблема

Парсеры эмитят «сырые» dict'ы: набор ключей почти единый (17 полей в
объединении по всем 31 сайту), но **значения непоследовательны**:

- **даты — строками в ≥4 форматах**: `26.08.2026 12:30 (33 дн.)`,
  `18.08.2026 13:00:00`, `29.07.2026 12:00`, `28.08.2026 00:00:00`;
- **`status`** — разный регистр/формулировки (`Прием заявок` / `объявлены`);
- **`detail`** — сырой label→value блоб, кириллические ключи, свои у каждого
  движка (1.4–8.5 КБ на лот);
- нет типов и валидации; ничто не ловит дрейф полей.

## 2. Модель `Lot` (pydantic v2, `collector/core/lot.py`)

```python
class Lot(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    source: str = Field(alias='_source')          # ключ парсера
    lot_id: str
    trade_id: str
    lot_num: str | None = None

    trade_title: str | None = None
    trade_type: str | None = None
    organizer: str | None = None

    description: str | None = None
    lot_url: str | None = None
    price: float | None = None
    price_raw: str | None = None

    status: str | None = None
    is_active: bool = True                         # derived из status
    bidding_deadline: datetime | None = None       # из bidding_date
    result_date: datetime | None = None            # из event_date
    bidding_date_raw: str | None = None
    event_date_raw: str | None = None

    attachments: list[dict] = Field(default_factory=list)
    price_schedule: list[dict] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict, alias='detail')
```

Поля 1:1 покрывают объединение 17 эмитируемых ключей (`_source`→`source`,
`detail`→`extra`; `bidding_date`/`event_date` перерабатываются валидатором в
пары normalized+raw). `extra='forbid'` — новое неизвестное поле от движка
уронит валидацию (дрейф виден сразу).

### 2.1. Нормализация (`@model_validator(mode='before')`)

```python
@model_validator(mode='before')
@classmethod
def _normalize(cls, data):
    if not isinstance(data, dict):
        return data
    d = dict(data)
    d['bidding_date_raw'] = d.get('bidding_date')
    d['bidding_deadline'] = parse_datetime(d.pop('bidding_date', None))
    d['event_date_raw'] = d.get('event_date')
    d['result_date'] = parse_datetime(d.pop('event_date', None))
    d.setdefault('is_active', is_active_status(d.get('status')))
    return d
```

- **`parse_datetime(raw)`** (новая, в `core/parsing.py`): убирает хвост `(…)`,
  парсит `DD.MM.YYYY[ HH:MM[:SS]]` → `datetime`; иначе `None`. Исходник всегда
  сохраняется в `*_raw`.
- **`is_active`** — через существующий `is_active_status(status)`.

## 3. Интеграция — модель течёт через границу

- **Парсеры** на выдаче отдают модель. Точки: `DiveParser.parse_lots_page`
  (kendo/btorg/ruson) и `fogsoft/base.py` (`parse` + `parse_detail`) —
  `yield Lot.model_validate(item)` вместо `yield item`. `Request`-объекты
  (пагинация/нырок) не оборачиваются.
- **`LotSink.save(item: Lot) -> ChangeStatus`** — контракт меняется с `dict`
  на `Lot`. `get_fingerprints` без изменений.
- **`BaseParser.crawl`/`process_item`** — item теперь `Lot`, не dict; проверить,
  что `process_item` не индексирует item как dict (счётчики идут через
  `ChangeStatus` из `save`).
- **Sink'и-потребители** дампят JSON: `main.py` и `worker.py` (`CollectingSink`)
  пишут `[lot.model_dump(mode='json') for lot in items]`. Тестовые `_Sink`
  принимают `Lot`.
- **`lot_fingerprint`** (в `contracts.py`) — **не трогаем**: используется только
  в `fogsoft.parse` на сырых строках листинга (до конвертации в `Lot`), там item
  остаётся dict'ом.

## 4. Затронутые файлы

| Файл | Изменение |
|---|---|
| `pyproject.toml` | + `pydantic>=2` в dependencies |
| `collector/core/lot.py` | новый — модель `Lot` + валидатор |
| `collector/core/parsing.py` | + `parse_datetime` |
| `collector/core/storage/sink.py` | `save(item: Lot)` |
| `collector/core/spider/dive.py` | `yield Lot.model_validate(item)` |
| `collector/sources/fogsoft/base.py` | обернуть оба `yield item` |
| `main.py`, `worker.py` | `CollectingSink` дампит `model_dump(mode='json')` |
| тесты интеграции | `_Sink` принимает `Lot`; ассерты на атрибуты, не на dict |

`parse_lots`/`parse_table` каждого движка **возвращают те же dict'ы** —
конвертация в `Lot` происходит на границе `parse_lots_page`/`parse`, поэтому
юнит-тесты парсеров не меняются.

## 5. Тесты

- `tests/unit/test_lot.py` (новый): `parse_datetime` на всех 4 форматах + мусоре
  `(33 дн.)`; `Lot.model_validate` реального item'а → `bidding_deadline`
  распарсен, `bidding_date_raw` сохранён, `is_active` выведен, `source`/`extra`
  через алиасы; `extra='forbid'` роняет неизвестное поле.
- `tests/unit/test_lot_all_engines.py` (новый): по одному сохранённому item'у на
  движок из фикстур **валидируется в `Lot`** без ошибок (гарантия, что forbid
  покрывает реальные ключи всех движков).
- Интеграционные краул-тесты: `_Sink.items` — теперь список `Lot`; ассерты
  `first.lot_id`, `first.price` (атрибуты).
- Прогон `uv run pytest` — зелёный; сети нет.

## 6. Definition of Done

- `Lot` в `core/lot.py`; парсеры эмитят `Lot`; `LotSink.save(item: Lot)`.
- Даты нормализованы в `datetime` (raw сохранён); `is_active` выведен.
- Все 31 движок-выход валидируется в `Lot` (проверено на фикстурах +
  живой smoke одного сайта на движок).
- `worker.py`/`main.py` пишут `model_dump(mode='json')`; JSON читаем, поля
  типизированы.
- `uv run pytest` зелёный; `pydantic>=2` в `pyproject`.

## 7. Следующие заходы (НЕ сейчас)

- Семантический дрейф: у centerr `trade_title` = должник, а не тип; выделить
  `debtor` отдельным полем; выровнять смысл `trade_title` по движкам.
- Разнести trade ↔ lots на сущности (сейчас торговые поля дублируются на лоте);
  вынести общий `detail`-блоб на уровень торгов.
- Маппинг `extra` (кириллические лейблы) в типизированные под-поля.
- БД-схема / версионированный внешний контракт.
