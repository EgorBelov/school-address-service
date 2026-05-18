# School Address Service

Веб-сервис для определения школы, к которой прикреплён адрес проживания, на основе муниципальных постановлений «О закреплении территорий за общеобразовательными организациями».

Курсовая работа. Реализована полная цепочка: загрузка постановления (`.doc` / `.docx` / `.pdf`) → извлечение текста (с OCR через ocr.space для сканов) → структурный парсинг таблиц (pdfplumber + PyMuPDF, python-docx) с регэксповым извлечением метаданных и LLM-помощником (GigaChat) для сложных правил → Pydantic-валидация → сохранение в БД → поиск школы по адресу с DaData-нормализацией (и регэксповым fallback при недоступности DaData).

---

## Содержание

1. [Что реализовано](#что-реализовано)
2. [Стек технологий](#стек-технологий)
3. [Структура проекта](#структура-проекта)
4. [Модель данных](#модель-данных)
5. [Pipeline обработки постановления](#pipeline-обработки-постановления)
6. [Стратегии парсинга](#стратегии-парсинга)
7. [Поиск школы по адресу](#поиск-школы-по-адресу)
8. [Извлечение метаданных](#извлечение-метаданных)
9. [Валидатор правил](#валидатор-правил)
10. [HTTP endpoints](#http-endpoints)
11. [CLI-утилиты](#cli-утилиты)
12. [Установка и запуск](#установка-и-запуск)
13. [Конфигурация (.env)](#конфигурация-env)
14. [Примеры использования](#примеры-использования)
15. [Известные ограничения](#известные-ограничения)
16. [Code review](#code-review)

---

## Что реализовано

### Пользовательская часть
- Главная страница с формой ввода адреса.
- Подсказки адресов через DaData с дебаунсом 300 мс.
- Нормализация адреса через DaData. Если DaData недоступна (TLS-timeout / нет ключа) — локальный regex-парсер.
- Поиск школы с учётом улицы, дома, чётности и диапазонов.
- Толерантный матч муниципалитета: `«Пермь»` ↔ `«Перми»`, `«Берёзники»` ↔ `«Березников»`.

### Админ-панель
- **Загрузка постановления** (`.doc` / `.docx` / `.pdf`) с извлечением текста и сохранением в `storage/decrees/`.
  - PDF: pdfplumber → OCR через ocr.space при необходимости.
  - DOCX: python-docx.
  - DOC: LibreOffice headless (`soffice --convert-to docx`); macOS fallback на `textutil`.
- **Универсальный парсинг**:
  - Структурное определение формата документа БЕЗ LLM (по форме таблиц в файле).
  - Многоколоночные таблицы «№ | Школа | Улица | Дома» (Пермский край) — парсятся структурно, **без обращения к LLM**.
  - Двухколоночные таблицы «Школа | Территория» (Балашиха) — структурно извлекаются строки, на каждую школу один LLM-запрос на разбор её территорий, плюс параллельный regex-fallback на случай пропусков LLM.
  - Файлы без таблиц (текстовые .doc) — целиком через LLM с retry/backoff на SSL/429.
- **Pydantic-валидация** ответов LLM с автоматической коэрсией типов.
- **Извлечение метаданных** (номер, дата, муниципалитет) регэкспом до LLM.
- **Сохранение** в БД с нормализацией значений (parity, диапазоны, exact-списки, исключения).
- **CRUD-таблица правил**, **отчёт валидатора** (пустые поля, некорректные диапазоны, пересечения между школами).

---

## Стек технологий

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| ORM / БД | SQLAlchemy 2.x, SQLite |
| Шаблоны | Jinja2 (server-side rendering) |
| Конфигурация | pydantic-settings, `.env` |
| Адресный сервис | DaData (`suggest`, `clean`) |
| LLM | GigaChat (Sber) с retry/backoff на SSL/429 |
| Валидация LLM-ответов | Pydantic v2 |
| Таблицы из PDF | pdfplumber (4 разные стратегии) + PyMuPDF fallback |
| Таблицы из DOCX | python-docx |
| `.doc` → `.docx` | LibreOffice headless / macOS textutil |
| OCR (для сканов) | ocr.space API |

---

## Структура проекта

```
school-address-service/
├── app/
│   ├── main.py                                # FastAPI-приложение, все endpoints
│   │
│   ├── core/
│   │   └── config.py                          # Pydantic Settings, .env
│   │
│   ├── db/
│   │   └── session.py                         # SQLAlchemy engine + SessionLocal
│   │
│   ├── models/
│   │   └── models.py                          # ORM: Municipality, School, Decree, AddressRule
│   │
│   ├── services/
│   │   ├── address/
│   │   │   ├── normalize.py                   # Нормализация улицы и локалити
│   │   │   └── local_parser.py                # Regex-парсер адреса (fallback к DaData)
│   │   │
│   │   ├── ai/gigachat/
│   │   │   ├── client.py                      # Конструктор GigaChat-клиента (retry, timeout)
│   │   │   ├── prompts.py                     # Промпт для парсинга постановления + few-shot
│   │   │   ├── schemas.py                     # Pydantic-модели ответов LLM
│   │   │   ├── retry.py                       # Общий retry/backoff на transient-ошибки
│   │   │   ├── decree_parser.py               # Чанк + LLM + merge + валидация
│   │   │   └── classifier/
│   │   │       └── document_classifier.py     # LLM-классификатор формата (резерв)
│   │   │
│   │   ├── dadata/
│   │   │   ├── client.py                      # DaData suggest/clean с try/except
│   │   │   └── street_validator.py            # Сверка улицы с DaData (с lru_cache)
│   │   │
│   │   ├── ocr/
│   │   │   └── ocr_space.py                   # OCR через ocr.space
│   │   │
│   │   ├── parser/
│   │   │   ├── text_extractor.py              # Текст из .doc/.docx/.pdf
│   │   │   ├── splitter.py                    # Разбиение текста на чанки по школам
│   │   │   ├── metadata_extractor.py          # Regex-извлечение №/даты/муниципалитета
│   │   │   ├── pdf_table_extractor.py         # Двухколоночные таблицы (Балашиха-style)
│   │   │   ├── docx_table_extractor.py        # DOCX-таблицы (использует process_table из pdf_)
│   │   │   ├── multi_column_extractor.py      # 4-колоночные таблицы (Пермь-style)
│   │   │   ├── territory_regex_fallback.py    # Regex-добор улиц, пропущенных LLM
│   │   │   ├── rule_normalizer.py             # parity / rule_type / range / exact_list / exceptions
│   │   │   ├── save_parsed_decree.py          # Сохранение в БД
│   │   │   ├── universal_parser.py            # Диспетчер стратегий (структурно → LLM)
│   │   │   └── strategies/
│   │   │       ├── base.py                    # ABC BaseParserStrategy
│   │   │       ├── two_column_parser.py       # «Школа | Территория» (PDF/DOCX + LLM на школу)
│   │   │       └── multi_column_parser.py     # «№ | Школа | Улица | Дома» (PDF/DOCX без LLM)
│   │   │
│   │   ├── search/
│   │   │   └── find_school.py                 # Алгоритм матчинга адреса с правилом
│   │   │
│   │   └── validation/
│   │       └── rules_validator.py             # Валидация правил + пересечения
│   │
│   └── templates/
│       ├── index.html                         # Главная (поиск школы)
│       ├── admin_upload.html                  # Загрузка + парсинг + сохранение
│       ├── admin_rules.html                   # CRUD-таблица правил
│       └── admin_validation.html              # Отчёт валидатора
│
├── storage/
│   ├── decrees/                               # Загруженные исходные файлы
│   └── extracted/                             # Извлечённый текст в .txt
│
├── example/                                   # Тестовые постановления
│   ├── проект.pdf                             # Балашиха (two_column)
│   ├── 06.03.2025-01-02-252.doc               # Берёзники (текстовый поток)
│   ├── 09.03.2021__142_…_.pdf                 # Перми (multi_column)
│   └── dat_1740743047951.docx                 # Перми (multi_column)
│
├── seed.py                                    # Тестовые данные (одна школа Берёзников)
├── reset_db.py                                # Полная очистка БД + seed
├── inspect_db.py                              # CLI-инспектор содержимого БД
├── requirements.txt
├── school_service.db                          # SQLite
├── .env                                       # Секреты (не коммитится)
├── .gitignore
└── README.md
```

---

## Модель данных

```
Municipality (1) ──< School (1) ──< AddressRule >── (1) Decree
                                       │
                                       └── locality, street, normalized_street,
                                           rule_type, parity,
                                           house_from, house_to,
                                           house_number, house_numbers, exceptions,
                                           comment,
                                           dadata_value, dadata_confidence,
                                           validation_status, validation_comment,
                                           house_rule_raw
```

| Таблица | Поля |
|---------|------|
| `municipalities` | `id`, `name`, `region` |
| `schools` | `id`, `municipality_id`, `name`, `address` |
| `decrees` | `id`, `municipality_id`, `number`, `date`, `file_path` |
| `address_rules` | `id`, `school_id`, `decree_id`, `locality`, `street`, `normalized_street`, `house_rule_raw`, `rule_type`, `parity`, `house_from`, `house_to`, `house_number`, `house_numbers`, `exceptions`, `comment`, `dadata_*`, `validation_*` |

**`house_rule_raw`** хранится всегда — это «сырой» текст правила из постановления, на случай ошибок парсинга.

**Поиск использует `rule.street`, а не `rule.normalized_street`** — последний DaData иногда нормализует в мусор (например, «шоссе Космонавтов» → «ГСК д-22 космонавтов»).

---

## Pipeline обработки постановления

```
            ┌─────────────────────┐
            │  Файл .doc / .docx  │
            │      / .pdf         │
            └──────────┬──────────┘
                       │
                       ▼
    ┌──────────────────────────────────┐
    │  text_extractor.extract_text()   │ ← диспетчер по расширению
    └──────────────────────────────────┘
        │            │              │
   .docx│       .pdf │         .doc │
        │            │              │
        ▼            ▼              ▼
  python-docx   pdfplumber    LibreOffice (soffice)
                (нативный)     → .docx → python-docx
                     │           (fallback: textutil
                     ▼            на macOS)
            если текст < 500 симв.
                     │
                     ▼
              ocr.space API
                     │
                     ▼
          ┌──────────────────┐
          │  Сырой текст +   │
          │  путь к файлу    │
          └────────┬─────────┘
                   │
                   ▼
   ┌──────────────────────────────────────┐
   │       universal_parser               │
   │       (диспетчер стратегий)          │
   │                                      │
   │   1. Структурная авто-детекция       │
   │      (без LLM!):                     │
   │      ├ is_multi_column_format(file)  │
   │      └ _is_two_column_format(file)   │
   │                                      │
   │   2. Если структурно не распознали:  │
   │      → LLM-классификатор             │
   └───────┬────────────────┬─────────────┘
           │                │
           ▼                ▼
   MultiColumnParser  TwoColumnParser
   (Пермь-style:      (Балашиха-style:
    структурно из     pdf+docx табл. +
    таблиц, БЕЗ LLM   LLM на каждую школу
    для типичных      + regex-fallback
    Пермских PDF/     по territory_text)
    DOCX)
           │                │
           └────────┬───────┘
                    ▼
        Pydantic-валидация ответа
        (DecreeResponseModel /
         TerritoryResponseModel)
                    │
                    ▼
              save_parsed_decree → БД
                    (DaData-сверка по улицам, с lru_cache)
```

---

## Стратегии парсинга

### `MultiColumnParserStrategy` — таблицы «№ | Школа | Улица | Дома»

Файлы: `strategies/multi_column_parser.py`, `multi_column_extractor.py`

Используется для постановлений Пермского края и аналогов, где каждая строка таблицы = одно правило. Школа повторяется во всех строках одной группы (или указывается только в первой).

Особенности:
- Поддерживает многостраничную таблицу: `current_school` пробрасывается между таблицами/страницами (continuation-строки на новой странице корректно привязываются к школе с предыдущей).
- Поддерживает алиасы улиц: `Монастырская (Орджоникидзе)` → 2 правила (новое имя + старое).
- Полностью **БЕЗ LLM** — все правила извлекаются регэкспами из таблицы.
- LLM-fallback только если структура файла не распознана.

### `TwoColumnParserStrategy` — таблицы «Школа | Территория»

Файлы: `strategies/two_column_parser.py`, `pdf_table_extractor.py`, `docx_table_extractor.py`

Используется для постановлений с длинным текстом территорий в одной ячейке (Балашиха-style).

Особенности:
- pdfplumber пробует 4 разных `table_settings` для каждой страницы; берётся вариант с наибольшим объёмом извлечённых данных (`_score_rows`).
- Если pdfplumber дал мало — fallback на PyMuPDF (`fitz`).
- Continuation-строки и разорванные между страницами имена школ склеиваются (`stitch_split_names`, `merge_duplicate_schools`).
- На каждую школу — LLM-запрос на её территории.
- **Параллельно** territory regex-fallback (`extract_rules_from_territory_text`) добавляет улицы, которые LLM пропустил. После сохранения `normalize_rule_fields` проставит им parity/rule_type.

### LLM-fallback по чистому тексту

Файл: `ai/gigachat/decree_parser.py`

Используется когда ни одна структурная стратегия не сработала (например, для текстового .doc Берёзников).

- Чанк по школам через `splitter.split_text_by_schools` (regex по нумерации `1.`, `4.1.`, `11.2.`).
- На каждый чанк отдельный LLM-вызов с retry/backoff (`gigachat/retry.py`).
- Промпт содержит **few-shot** примеры разных типов правил.
- Метаданные постановления добираются регэкспом.

---

## Поиск школы по адресу

Файл: `services/search/find_school.py`

1. Адрес нормализуется DaData (или локальным regex-парсером, если DaData молчит).
2. Извлекаются `city` / `street` / `house`.
3. Все правила загружаются и фильтруются по трём критериям:
   - **Улица**: `normalize_street_name(rule.street) == normalize_street_name(target_street)` — обе стороны нормализуются (убираются «ул.», «пр-кт», «шоссе», «мкр.» и т.п. через regex с `\b`-границами).
   - **Локалити**: толерантный матч (`_locality_match`): общий префикс ≥4 символа + допуск 1–2 на хвост падежного окончания. `«Пермь»` ↔ `«Перми»` ↔ `«Перму»`. Сравниваются и `rule.locality`, и `rule.school.municipality.name`.
   - **Дом**: `is_house_matches` — учитывает `exceptions`, `house_numbers`/`house_number` (exact_list), `parity`, `from..to`, `up_to`, `from_to_end`.

---

## Извлечение метаданных

Файл: `services/parser/metadata_extractor.py`

Регэкспы на первых ~3000 символах документа достают:

- **Номер** (`№ 01-02-252`, `N 171-ПА`).
- **Дата** (`06.03.2025`, `6 марта 2025`, с поддержкой текстовых месяцев).
- **Муниципалитет** (`Городск(ой|ого) округ X`, `город X`, `муниципальный район X`).

Фильтр «чужого контекста» отсекает ссылки на ФЗ / приказы Минпросвещения / отменённые постановления:

```python
_FOREIGN_CONTEXT_RE = re.compile(
    r"\b(ФЗ|ФКЗ|РФ|закон|приказ|министерств|"
    r"постановлени\w+\s+правительств|"
    r"утративш\w+\s+силу|признать\s+утративш)",
    re.IGNORECASE,
)
```

Используется как **seed** для метаданных decree: LLM может уточнить, но если он молчит — берётся регэксповый результат.

---

## Валидатор правил

Файл: `services/validation/rules_validator.py`

| Тип | Уровень | Что проверяет |
|-----|---------|---------------|
| `empty_street` | error | Не указана улица |
| `empty_house_rule` | warning | Пустой текст правила |
| `invalid_range` | error | `house_from > house_to` |
| `unknown_parity` | warning | Чётность не из списка `all/even/odd/mixed/unknown` |
| `intersection` | error | Два правила разных школ покрывают один дом на одной улице |

---

## HTTP endpoints

### Публичные

| Метод | Путь | Параметры | Описание |
|-------|------|-----------|----------|
| `GET` | `/` | — | Главная: форма поиска. |
| `POST` | `/search` | `address` (form) | Поиск школы. DaData → fallback на local_parser → поиск в БД. |
| `GET` | `/api/address/suggest` | `q` | Прокси к DaData suggest для автокомплита. |

### Админка

| Метод | Путь | Параметры | Описание |
|-------|------|-----------|----------|
| `GET` | `/admin/upload` | — | Страница загрузки. |
| `POST` | `/admin/upload` | `file` (multipart) | Сохраняет файл и извлекает текст. Возвращает `text` и `file_path` в шаблон. |
| `POST` | `/admin/parse-with-ai` | `text`, `file_path` | Запускает `parse_document_universal` (структурная детекция → стратегия → Pydantic). |
| `POST` | `/admin/save-parsed` | `parsed_json` | Сохраняет результат в БД. |
| `GET` | `/admin/rules` | — | CRUD-таблица всех правил. |
| `POST` | `/admin/rules/update/{rule_id}` | поля правила | Обновление правила. |
| `POST` | `/admin/rules/delete/{rule_id}` | — | Удаление правила. |
| `GET` | `/admin/validation` | — | Отчёт валидатора. |

Swagger / ReDoc: `/docs`, `/redoc`.

---

## CLI-утилиты

```bash
python seed.py            # тестовые данные (Берёзники, школа № 2)
python reset_db.py        # полная очистка БД + seed
python inspect_db.py      # сводка по муниципалитетам/школам/правилам
python inspect_db.py Монастырская                          # все правила по улице
python inspect_db.py --school "школа № 32"                 # все правила школы
python inspect_db.py --check "г Пермь, Монастырская, 96"   # симуляция поиска
```

---

## Установка и запуск

### 1. Системные зависимости

**LibreOffice** — для конвертации `.doc` → `.docx` (на Linux обязательно, на macOS опционально):

```bash
# macOS:
brew install libreoffice

# Linux (Ubuntu/Debian):
sudo apt-get install -y libreoffice-writer
```

OCR работает через облачный **ocr.space**, локальный Tesseract не требуется.

### 2. Python-окружение

```bash
git clone <repo-url>
cd school-address-service

python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Конфигурация

Создайте `.env` (см. ниже).

### 4. Заполнить БД тестовыми данными

```bash
python seed.py
```

### 5. Запуск

```bash
uvicorn app.main:app --reload
```

Открыть `http://127.0.0.1:8000`.

---

## Конфигурация (.env)

```env
DATABASE_URL=sqlite:///./school_service.db

DADATA_TOKEN=ваш_токен
DADATA_SECRET=ваш_секрет

GIGACHAT_CREDENTIALS=ваш_authorization_key
GIGACHAT_VERIFY_SSL_CERTS=false

# Демо-ключ "helloworld" имеет лимиты
OCR_SPACE_API_KEY=helloworld
```

Относительный путь `sqlite:///./school_service.db` автоматически резолвится в абсолютный относительно корня проекта (см. `app/core/config.py`) — это нужно, чтобы uvicorn `--reload` не «терял» БД при смене cwd.

---

## Примеры использования

### Поиск школы

1. Открыть `http://127.0.0.1:8000`.
2. Ввести адрес, например `г Пермь, ул Монастырская, д 96`.
3. Получить: `МАОУ «СОШ № 32 им. Г.А. Сборщикова»`, правило-основание.

### Загрузка нового постановления

1. `http://127.0.0.1:8000/admin/upload` → выбрать файл.
2. «Распарсить через GigaChat»:
   - **Пермский PDF / DOCX (multi_column)** — парсится мгновенно, без вызовов GigaChat.
   - **Балашиха-PDF (two_column)** — 36 LLM-запросов (по одному на школу), с паузой 2.5 с и retry/backoff на SSL/429.
   - **Берёзники .doc (текст)** — LLM по чанкам с retry.
3. Проверить JSON, сохранить в БД.
4. `/admin/rules` — увидеть правила, `/admin/validation` — проверить пересечения.

---

## Известные ограничения

Это учебный проект, поэтому не реализовано:

- Нет аутентификации админки — все `/admin/*` открыты.
- БД — SQLite (для одного пользователя ок).
- LLM/OCR работают синхронно в HTTP-запросе.
- Поиск загружает все правила в Python (для учебного объёма ~1000 — ок).
- `.doc` без LibreOffice работает только на macOS (`textutil`).
- Дата постановления хранится строкой (`String`), а не `Date`.
- Нет автоматических тестов и миграций (Alembic).
- Нет структурного логирования и мониторинга.

---

## Code review

### Сильные стороны

1. **Слоистая структура `services/<domain>/`** с чёткими ответственностями: `parser/`, `search/`, `validation/`, `address/`, `dadata/`, `ai/`, `ocr/`.
2. **Структурный парсинг до LLM**. Многоколоночные постановления (Пермь) обрабатываются полностью regex'ами без обращения к GigaChat — это быстро, бесплатно и надёжно.
3. **Гибкий диспетчер стратегий**. `universal_parser` сначала пытается определить формат файла по структуре таблиц, и только если не получилось — спрашивает у LLM-классификатора.
4. **Универсальный retry/backoff** для GigaChat (`ai/gigachat/retry.py`) с классификатором transient-ошибок (SSL/EOF/429/5xx). Один модуль на все вызовы.
5. **Pydantic-валидация ответов LLM** с автокоэрсией типов: `"19"` → `19`, `["21","23"]` → `"21,23"`, `null` → `""`.
6. **Regex-fallback на territory_text**: даже если LLM пропустил часть улиц, парсер добавляет их «сырыми» правилами, и `normalize_rule_fields` доразбирает их.
7. **Толерантный матч локали** (`_locality_match`) — корректно обрабатывает падежи и букву «ё», что важно для пользовательского ввода.
8. **Локальный fallback-парсер адреса** (`local_parser.py`) — `/search` работает даже при недоступной DaData.
9. **lru_cache на DaData**-запросах — одна и та же улица не запрашивается дважды при сохранении 700+ правил.
10. **CLI-утилиты** (`reset_db.py`, `inspect_db.py`) — удобны для дебага БД и проверки результата парсинга.

### Что стоит улучшить

#### Критично

- **Нет аутентификации `/admin/*`** — любой может удалить правила. Минимально нужно HTTP Basic Auth или CSRF + сессии.
- **Path traversal в `/admin/upload`** — `file_path = upload_dir / file.filename` без санитайзинга. Файл с именем `../../etc/passwd` запишет куда угодно. Заменить на `secure_filename` + UUID-префикс.
- **`.env` лежит в репозитории** (не в gitignore по факту?). После курсовой обязательно отозвать DaData/GigaChat-токены.

#### Архитектурно

- **`Decree.date` хранится строкой** — поломает любую сортировку по дате. Перевести в `Date`.
- **`find_school_by_address` грузит ВСЕ правила** в Python. Для учебного масштаба ок, но для прода нужно фильтровать в SQL по `normalized_street` + индекс. Сейчас `normalized_street` поле есть, но используется неправильно (часто содержит мусор от DaData).
- **Нет миграций (Alembic)** — `Base.metadata.create_all` на старте. Любое изменение схемы потребует ручного удаления БД.
- **Нет тестов**. Минимально стоит написать unit'ы на чистые функции: `_locality_match`, `is_house_matches`, `normalize_rule_fields`, `extract_rules_from_territory_text`, `parse_address_locally`, `extract_decree_metadata` — это покроет ~70% логики.

#### Среднее

- **Хардкод `region=None`** в `_get_or_create_municipality`. Если хочется хранить регион — извлекать его из шапки постановления.
- **`splitter.split_text_by_schools`** жёстко завязан на нумерацию пунктов вида `\n  1.\n`. Для постановлений с другой структурой даст 1 чанк (а потом обрежется до 4000 символов).
- **`DECREE_PARSE_PROMPT` обрезает чанк до 4000 символов**. Если в одной школе очень длинная территория — потеряется хвост. Лучше: чанкинг на уровне расширенного промпта или multiple turns.
- **`document_classifier`** сейчас почти не используется (структурная детекция надёжнее). Можно удалить или оставить как страховку.
- **Адрес школы из LLM** часто содержит мусор. `sanitize_school_address` отбрасывает явные случаи, но в БД иногда всё равно записывается территория. Лучше: вообще не доверять `address` от LLM, оставлять пустым и заполнять руками в админке.
- **Нет `__init__.py`** в пакетах — Python 3 работает через implicit namespace packages, но это не рекомендуется для приложений (могут возникать сюрпризы с IDE и линтерами).

#### Минорное

- **Шаблоны без общего base.html** — стили дублируются в 4 HTML-файлах. Любое изменение цвета — править 4 места.
- **Невалидный HTML в `admin_rules.html`** — `<form>` начинается внутри `<tr>` и заканчивается посреди `<td>`. Современные браузеры терпят, но лучше переделать на одну форму с `<button name="action" value="...">`.
- **`requirements.txt`** включает `textract`, `extract-msg`, `oletools`, `easygui`, `SpeechRecognition`, `xlrd`, `xlsxwriter`, `python-pptx`, `RTFDE` — почти все не используются. Это результат `pip freeze`. Можно сильно сократить.
- **Логирование через `print()`** вместо `logging`. Для прода нужен JSON-логгер.

### Что НЕ стоит трогать

- Структуру `services/<domain>/` — она правильная.
- Two-step парсинг (структурный extractor → LLM на сложное) — это правильное архитектурное решение.
- Толерантный матч локали и regex-fallback на territory — практичные инженерные хаки для домена с грязными данными.

---

## Финальная оценка как учебного проекта: 7/10

Сильно выше типичной курсовой за счёт:
- структурного парсинга PDF/DOCX без LLM,
- осознанной работы с LLM-нестабильностью (retry, Pydantic-валидация, regex-fallback),
- продуктовой логики (толерантный матч локали, склейка алиасов улиц, валидация пересечений правил),
- утилит для разработки (`reset_db.py`, `inspect_db.py`).

Чего не хватает до production:
- auth + CSRF + path-traversal-фикс,
- тестов,
- миграций (Alembic),
- структурного логирования,
- асинхронной обработки тяжёлых операций (OCR/LLM в фоне).
