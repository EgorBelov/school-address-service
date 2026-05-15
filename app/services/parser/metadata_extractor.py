"""
Дешёвое извлечение метаданных постановления (номер, дата, муниципалитет)
регулярными выражениями. Запускается ДО вызова LLM — освобождает модель от
рутины и страхует на случай, когда она их не вытянула.
"""
import re


# ── Номер постановления: «№ 01-02-252», «N 171-ПА», «№ 458» ─────────────
NUMBER_RE = re.compile(
    r"(?:№|N)\s*([\d]+(?:[\-/.][\dА-Яа-я]+)*)",
    re.IGNORECASE,
)


# ── Числовая дата: 06.03.2025, 6/3/25, 06-03-2025 ────────────────────────
DATE_NUMERIC_RE = re.compile(
    r"\b(\d{1,2})[.\s/-](\d{1,2})[.\s/-](\d{2,4})\b"
)


# ── Текстовая дата: «6 марта 2025» ───────────────────────────────────────
MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5,
    "июн": 6, "июл": 7, "август": 8, "сентябр": 9,
    "октябр": 10, "ноябр": 11, "декабр": 12,
}

DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма[йя]|июн\w*|июл\w*|"
    r"август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s+"
    r"(\d{4})",
    re.IGNORECASE,
)


# ── Муниципалитет: «Городского округа Балашиха», «город Пермь»,
#    «муниципальный район Пушкинский», «городской округ Электросталь» ────
# Префикс — case-insensitive (inline-флаг), но capture group остаётся
# case-sensitive: имя муниципалитета должно начинаться с заглавной буквы.
MUNICIPALITY_RE = re.compile(
    r"(?i:"
    r"Городск(?:ой|ого)\s+округ(?:а)?|"
    r"город(?:а|ского)?(?!\s+округ)|"
    r"муниципальн\w+\s+(?:район(?:а)?|округ(?:а)?)"
    r")\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)?)",
)


def _head(text: str, limit: int = 3000) -> str:
    return text[:limit] if text else ""


# Контекст-маркеры, по которым отличаем дату/номер ПОСТАНОВЛЕНИЯ
# от даты/номера федерального закона, приказа Минпросвещения и т.п.
_FOREIGN_CONTEXT_RE = re.compile(
    r"\b("
    r"ФЗ|ФКЗ|РФ|"
    r"закон|приказ|министерств|"
    r"постановлени\w+\s+правительств|"
    r"утративш\w+\s+силу|признать\s+утративш"
    r")",
    re.IGNORECASE,
)


def _is_foreign_context(text: str, start: int, end: int) -> bool:
    """
    Не относится ли число к чужому документу: ФЗ, приказу, отменённому
    постановлению. Окно слева больше — фразы вроде «Признать утратившим
    силу постановление … от 05.03.2022 № 171-ПА» бывают длинные.
    """
    around = text[max(0, start - 150):end + 30]
    return bool(_FOREIGN_CONTEXT_RE.search(around))


def extract_decree_number(text: str) -> str:
    head = _head(text)

    for match in NUMBER_RE.finditer(head):
        if _is_foreign_context(head, match.start(), match.end()):
            continue
        return match.group(1).strip(".-/")

    return ""


def extract_decree_date(text: str) -> str:
    head = _head(text)

    for match in DATE_NUMERIC_RE.finditer(head):
        if _is_foreign_context(head, match.start(), match.end()):
            continue
        day, month, year = match.groups()
        if len(year) == 2:
            year = "20" + year
        try:
            return f"{int(day):02d}.{int(month):02d}.{int(year):04d}"
        except ValueError:
            continue

    for match in DATE_TEXT_RE.finditer(head):
        if _is_foreign_context(head, match.start(), match.end()):
            continue
        day, month_word, year = match.groups()
        month_word_lower = month_word.lower()
        for prefix, num in MONTHS.items():
            if month_word_lower.startswith(prefix):
                return f"{int(day):02d}.{num:02d}.{int(year):04d}"

    return ""


def extract_municipality(text: str) -> str:
    match = MUNICIPALITY_RE.search(_head(text))
    if not match:
        return ""
    return match.group(1).strip()


def extract_decree_metadata(text: str) -> dict:
    return {
        "number": extract_decree_number(text),
        "date": extract_decree_date(text),
        "municipality": extract_municipality(text),
    }
