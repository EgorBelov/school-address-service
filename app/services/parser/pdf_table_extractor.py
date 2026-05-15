import re
import pdfplumber


# ───────────────────────── Регэкспы и хелперы ─────────────────────────

SCHOOL_NAME_RE = re.compile(
    r"«[^»]*(?:школа|школа-интернат|прогимназия|гимназия|лицей|СОШ|НОШ|ООШ)[^»]*»",
    re.IGNORECASE,
)

# Юридические префиксы школ: муниципальные, государственные, автономные,
# частные, некоммерческие.
SCHOOL_PREFIX_RE = re.compile(
    r"^\s*("
    r"Муниципальн|Государственн|"
    r"МБОУ|МАОУ|МОУ|МКОУ|МАУ|"
    r"ГБОУ|ГАОУ|ГОУ|ГКОУ|"
    r"АНО|АНОО|ОАНО|ЧОУ|НОУ|"
    r"СОШ|НОШ|ООШ"
    r")",
    re.IGNORECASE,
)

# Когда имя школы разорвано между страницами, продолжение обычно
# начинается со слов «Городского округа …» или просто «"...школа № N"».
SCHOOL_NAME_CONTINUATION_RE = re.compile(
    r"^\s*(Городск(ого|ой)|«)",
    re.IGNORECASE,
)

TERRITORY_MARKER_RE = re.compile(
    r"\b("
    # Сокращения улиц и проездов
    r"ул\.|пр-кт|пр-т|пр\.|просп\.|проспект|шоссе|ш\.|"
    r"пер\.|переулок|проезд|пр-д|"
    r"бульвар|б-р|"
    r"наб\.|набережная|"
    r"дор\.|дорога|тракт|"
    r"аллея|площадь|пл\.|тупик|"
    # Микрорайоны и территории
    r"мкр\.|мкрн\.|мкрн|микрорайон|"
    r"квартал|кв-л|"
    r"тер\.|территория|"
    r"линия|просек|просека|"
    r"городок|"
    # Населённые пункты
    r"д\.|с\.|п\.|г\.|ст\.|пос\.|"
    r"деревня|село|посёлок|поселок|станция|"
    # Садовые и дачные товарищества, ЖК, прочие
    r"СНТ|ТСН|ДНП|ДНТ|ДНС|ДПК|КП|"
    r"ЖК|ЖСК|ЖСТ|"
    r"СПО|ПК\s*СТ|ПО\s*СТ|СТ\s|"
    # Прямое упоминание дома
    r"дом\s+\d|д\.\s*\d"
    r")",
    re.IGNORECASE,
)


def clean(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("­", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_school_cell(text: str | None) -> bool:
    """
    Ячейка считается «началом школы», если содержит каноническую
    кавычечную часть «...школа/гимназия/лицей...» ИЛИ начинается
    с «Муниципальн…» и достаточно короткая (это не тело документа).
    """
    if not text:
        return False

    text = text.strip()

    if not text or len(text) > 600:
        return False

    if "Наименование" in text:
        return False

    if SCHOOL_NAME_RE.search(text):
        return True

    if SCHOOL_PREFIX_RE.match(text) and len(text) < 250:
        return True

    return False


def is_territory_text(text: str | None) -> bool:
    if not text:
        return False
    if len(text.strip()) < 3:
        return False
    return bool(TERRITORY_MARKER_RE.search(text))


def is_same_school(name_a: str, name_b: str) -> bool:
    """
    Считаем две школы одной и той же, если каноническая часть имени
    («…школа № N» / «Гимназия № N» / «Лицей № N» в кавычках) совпадает,
    либо если одна строка целиком содержится в другой.
    """
    if not name_a or not name_b:
        return False

    a = name_a.strip()
    b = name_b.strip()

    if a == b:
        return True

    if a in b or b in a:
        return True

    quote_a = SCHOOL_NAME_RE.search(a)
    quote_b = SCHOOL_NAME_RE.search(b)

    if quote_a and quote_b:
        return quote_a.group(0).lower() == quote_b.group(0).lower()

    return False


def merge_row_cells(cells: list) -> str:
    """
    Принимает список ячеек одной строки. Возвращает склейку
    непустых ячеек по порядку, но без подстрок: если одна ячейка
    полностью содержится в другой (более длинной), её отбрасываем.
    """
    cleaned = [clean(c) for c in cells]
    cleaned = [c for c in cleaned if c]

    if not cleaned:
        return ""

    by_length_desc = sorted(set(cleaned), key=len, reverse=True)
    keep: list[str] = []

    for candidate in by_length_desc:
        if any(candidate in larger for larger in keep):
            continue
        keep.append(candidate)

    keep_set = set(keep)
    seen: set[str] = set()
    ordered: list[str] = []

    for c in cleaned:
        if c in keep_set and c not in seen:
            ordered.append(c)
            seen.add(c)

    return " ".join(ordered)


# ───────────────────────── Обработка таблицы ─────────────────────────

def process_table(table: list[list], page_index: int) -> list[dict]:
    """
    Превращает одну таблицу pdfplumber в список записей
    {school_name, territory_text, page}. Continuation-строки
    (без школы, но с территорией) приклеиваются к текущей школе.
    """
    rows_out: list[dict] = []
    current: dict | None = None

    for raw_row in table:
        if raw_row is None:
            continue

        # Найти первую ячейку, похожую на школу
        school_idx = None
        for i, cell in enumerate(raw_row):
            if is_school_cell(cell):
                school_idx = i
                break

        if school_idx is not None:
            other_cells = [
                c for i, c in enumerate(raw_row) if i != school_idx
            ]
            territory_cells = [
                c for c in other_cells if is_territory_text(c)
            ]
            new_school_name = clean(raw_row[school_idx])

            # Если в строке нашлось имя школы, но рядом нет территории, —
            # это, скорее всего, фрагмент разорванного имени той же
            # школы (или соседней ячейки), а не начало новой записи.
            # Не сбрасываем current.
            if not territory_cells:
                continue

            # Если «новое» имя — это просто короткий фрагмент текущего
            # (например, current="… «Гимназия № 11»", new="«Гимназия № 11»"),
            # таблица была разорвана на сабстроки. Это та же школа,
            # территорию добавляем к текущей.
            if current and is_same_school(new_school_name, current["school_name"]):
                addition = merge_row_cells(territory_cells)
                if addition and addition not in current["territory_text"]:
                    current["territory_text"] = (
                        current["territory_text"] + " " + addition
                    ).strip()
                continue

            if current and current["territory_text"]:
                rows_out.append(current)

            current = {
                "page": page_index,
                "school_name": new_school_name,
                "territory_text": merge_row_cells(territory_cells),
            }
            continue

        # Continuation-строка: ищем территорию в любых ячейках
        territory_pieces = [
            c for c in raw_row if is_territory_text(c)
        ]

        if not territory_pieces or current is None:
            continue

        addition = merge_row_cells(territory_pieces)

        if not addition:
            continue

        # Не дублируем уже добавленный текст
        if addition in current["territory_text"]:
            continue

        current["territory_text"] = (
            current["territory_text"] + " " + addition
        ).strip()

    if current and current["territory_text"]:
        rows_out.append(current)

    return rows_out


# ───────────────────────── Слияние имён, разорванных между страницами ─────────────────────────

def stitch_split_names(rows: list[dict]) -> list[dict]:
    """
    На границе страниц pdfplumber иногда выдаёт имя школы двумя
    кусками: «Муниципальное автономное общеобразовательное учреждение»
    в конце страницы N и «Городского округа Балашиха "Школа № X"»
    в начале страницы N+1. Если имя без закрывающей «»» сразу
    предшествует записи без территории, начинающейся с продолжения, —
    склеиваем.
    """
    stitched: list[dict] = []

    for row in rows:
        if (
            stitched
            and "»" not in stitched[-1]["school_name"]
            and SCHOOL_NAME_CONTINUATION_RE.match(row["school_name"])
        ):
            previous = stitched[-1]
            previous["school_name"] = clean(
                previous["school_name"] + " " + row["school_name"]
            )

            if row["territory_text"]:
                if previous["territory_text"]:
                    previous["territory_text"] = clean(
                        previous["territory_text"] + " " + row["territory_text"]
                    )
                else:
                    previous["territory_text"] = row["territory_text"]

            continue

        stitched.append(row)

    return stitched


def merge_duplicate_schools(rows: list[dict]) -> list[dict]:
    """
    Одна и та же школа может встретиться в нескольких таблицах
    (фрагменты на разных страницах). Оставляем по одной записи —
    с самой длинной территорией.
    """
    by_name: dict[str, dict] = {}

    for row in rows:
        name = row["school_name"]

        if name not in by_name:
            by_name[name] = row
            continue

        existing = by_name[name]

        if len(row["territory_text"]) > len(existing["territory_text"]):
            by_name[name] = row

    return list(by_name.values())


# ───────────────────────── Стратегии извлечения ─────────────────────────

# Несколько настроек pdfplumber. По умолчанию pdfplumber использует
# `lines` для обеих осей, что не находит безграничные таблицы. Прогоним
# страницу несколькими стратегиями и возьмём лучший результат.
_PDFPLUMBER_TABLE_STRATEGIES = [
    None,  # дефолт
    {"vertical_strategy": "lines", "horizontal_strategy": "lines",
     "snap_tolerance": 4},
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "snap_tolerance": 4},
    {"vertical_strategy": "lines", "horizontal_strategy": "text",
     "snap_tolerance": 4},
]


def _filter_meaningful(rows: list[dict]) -> list[dict]:
    """Имя должно быть осмысленным, территория — длиннее ~10 символов."""
    return [
        row for row in rows
        if len(row["territory_text"]) >= 10
        and (
            SCHOOL_NAME_RE.search(row["school_name"])
            or "учреждение" in row["school_name"].lower()
        )
    ]


def _score_rows(rows: list[dict]) -> int:
    """
    «Качество» извлечения: суммарная длина territory_text по всем
    осмысленным записям. Фрагментированные таблицы дают много пустых
    «школ», но мало данных — и проигрывают целому разбиению.
    """
    return sum(
        len(r["territory_text"])
        for r in rows
        if SCHOOL_NAME_RE.search(r["school_name"])
        or "учреждение" in r["school_name"].lower()
    )


def _extract_with_pdfplumber(file_path: str) -> list[dict]:
    rows: list[dict] = []

    with pdfplumber.open(file_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            best_for_page: list[dict] = []
            best_score = 0

            for settings in _PDFPLUMBER_TABLE_STRATEGIES:
                try:
                    tables = (
                        page.extract_tables(table_settings=settings)
                        if settings else page.extract_tables()
                    ) or []
                except Exception:
                    continue

                attempt: list[dict] = []
                for table in tables:
                    attempt.extend(process_table(table, page_index))

                score = _score_rows(attempt)
                if score > best_score:
                    best_score = score
                    best_for_page = attempt

            rows.extend(best_for_page)

    return rows


def _extract_with_pymupdf(file_path: str) -> list[dict]:
    """
    PyMuPDF (`fitz`) часто справляется с таблицами без линий лучше pdfplumber.
    Если пакет не установлен — тихо возвращаем пусто.
    """
    try:
        import pymupdf as fitz  # >=1.24
    except ImportError:
        try:
            import fitz  # старый импорт
        except ImportError:
            return []

    rows: list[dict] = []

    try:
        doc = fitz.open(file_path)
    except Exception:
        return []

    try:
        for page_index, page in enumerate(doc, start=1):
            try:
                tabs = page.find_tables()
            except Exception:
                continue

            tables_list = getattr(tabs, "tables", None) or list(tabs)

            for tab in tables_list:
                try:
                    raw = tab.extract()
                except Exception:
                    continue
                if raw:
                    rows.extend(process_table(raw, page_index))
    finally:
        doc.close()

    return rows


def extract_by_tables(file_path: str) -> list[dict]:
    """
    Достаём строки из таблиц PDF, пробуя по очереди несколько движков:
    1. pdfplumber с разными table_settings;
    2. PyMuPDF (если установлен) — спасает на borderless-таблицах.
    Берём результат с бóльшим числом «осмысленных» школ.
    """
    plumber_rows = _extract_with_pdfplumber(file_path)
    plumber_meaningful = _filter_meaningful(
        merge_duplicate_schools(stitch_split_names(plumber_rows))
    )

    # Если pdfplumber дал мало — пробуем PyMuPDF и сравниваем
    if len(plumber_meaningful) < 3:
        fitz_rows = _extract_with_pymupdf(file_path)
        fitz_meaningful = _filter_meaningful(
            merge_duplicate_schools(stitch_split_names(fitz_rows))
        )

        if len(fitz_meaningful) > len(plumber_meaningful):
            print(
                f"[pdf_table_extractor] PyMuPDF выиграл: "
                f"{len(fitz_meaningful)} vs pdfplumber {len(plumber_meaningful)}"
            )
            return fitz_meaningful

    return plumber_meaningful


def extract_by_two_columns(file_path: str) -> list[dict]:
    """
    Fallback на случай, когда pdfplumber вообще не находит таблицы
    (например, PDF свёрстан текстовыми блоками без линий). Режем
    страницу пополам и пытаемся выделить блоки школ слева и
    территории справа.
    """
    rows: list[dict] = []

    with pdfplumber.open(file_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            if page_index == 1:
                continue

            width = page.width
            height = page.height

            left_crop = page.crop((0, 0, width * 0.42, height))
            right_crop = page.crop((width * 0.38, 0, width, height))

            left_text = clean(left_crop.extract_text())
            right_text = clean(right_crop.extract_text())

            if not left_text or not right_text:
                continue

            school_parts = re.split(
                r"(?="
                r"Муниципальн(?:ое|ому|ого)\s+(?:бюджетн|автономн|казённ|казенн)|"
                r"Государственн(?:ое|ому|ого)\s+(?:бюджетн|автономн|казённ|казенн)|"
                r"\b(?:МБОУ|МАОУ|МОУ|МКОУ|ГБОУ|ГАОУ|ГОУ|ГКОУ|АНО|АНОО|ОАНО|ЧОУ|НОУ)\b"
                r")",
                left_text,
            )

            right_parts = re.split(
                r"(?=мкр\.|мкрн|микрорайон|ул\.|пр-кт|пр-т|проспект|шоссе|"
                r"д\.|с\.|п\.|г\.|пер\.|проезд|бульвар|б-р|"
                r"квартал|тер\.|территория|"
                r"СНТ|ТСН|ДНП|ДНТ|ДПК|КП|ЖК|ЖСК)",
                right_text,
            )

            schools = [clean(p) for p in school_parts if SCHOOL_NAME_RE.search(p)]

            territories = [
                clean(p) for p in right_parts if len(clean(p)) > 20
            ]

            count = min(len(schools), len(territories))

            for i in range(count):
                rows.append({
                    "page": page_index,
                    "school_name": schools[i],
                    "territory_text": territories[i],
                })

    return rows


def extract_school_table_rows_from_pdf(file_path: str) -> list[dict]:
    rows = extract_by_tables(file_path)

    if rows:
        print(f"[pdf_table_extractor] rows by tables: {len(rows)}")
        return rows

    rows = extract_by_two_columns(file_path)
    print(f"[pdf_table_extractor] rows by columns: {len(rows)}")

    return rows
