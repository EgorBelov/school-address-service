"""
Локальный fallback-парсер адреса. Запускается, когда DaData недоступна
(SSL timeout / выключена / нет ключа). Не претендует на точность DaData,
но достаточно надёжно вытаскивает локалити / улицу / дом из формата
типа «Московская обл, г Балашиха, ул Ленина, д 42».
"""
import re


# Маркеры типов улиц — используем для определения, что идёт следом улица.
# ВАЖНО: «мкр»/«микрорайон»/«квартал» — это НЕ улица, а часть локалити.
_STREET_TYPE_RE = re.compile(
    r"\b(улица|ул|проспект|пр-кт|пр-т|просп|пр|"
    r"шоссе|ш|бульвар|б-р|переулок|пер|проезд|пр-д|"
    r"набережная|наб|площадь|пл|тупик|туп|аллея|линия|тракт)\b\.?",
    re.IGNORECASE,
)

# Маркеры микрорайона / квартала — это не улица.
_DISTRICT_TYPE_RE = re.compile(
    r"\b(мкр|мкрн|микрорайон|квартал|кв-л)\b\.?",
    re.IGNORECASE,
)

# Маркеры населённого пункта.
_LOCALITY_TYPE_RE = re.compile(
    r"\b(г|город|пос|посёлок|поселок|с|село|д|деревня|пгт)\b\.?",
    re.IGNORECASE,
)

# Маркеры дома.
_HOUSE_TYPE_RE = re.compile(r"\b(д|дом|строение|стр|корп|корпус)\b\.?", re.IGNORECASE)


def _strip_house_prefix(value: str) -> str:
    """«д 42», «дом 42», «д.42», «42» → «42»."""
    value = value.strip()
    value = _HOUSE_TYPE_RE.sub("", value, count=1).strip()
    return value


def _strip_locality_prefix(value: str) -> str:
    """«г Балашиха», «город Балашиха» → «Балашиха»."""
    value = value.strip()
    value = _LOCALITY_TYPE_RE.sub("", value, count=1).strip()
    return value


def _strip_street_prefix(value: str) -> str:
    """«ул Ленина», «проспект Ленина», «шоссе Энтузиастов» → «Ленина»/«Энтузиастов»."""
    value = value.strip()
    value = _STREET_TYPE_RE.sub("", value, count=1).strip()
    return value


def parse_address_locally(address: str) -> dict:
    """
    Простой парсер адреса по запятым. Возвращает dict в формате,
    совместимом с DaData (поля city/settlement/street/house/result).
    Не идеален — но позволяет работать поиску, когда DaData молчит.
    """
    if not address:
        return {}

    parts = [p.strip() for p in re.split(r"[,\n]", address) if p.strip()]

    result_locality = ""
    result_street = ""
    result_house = ""

    for part in parts:
        lowered = part.lower()

        # Регион — обычно "Московская обл" / "Пермский край". Игнорируем.
        if re.search(r"\b(обл|область|край|респ|республика)\b\.?", lowered):
            continue

        # Дом: «д 42», «д. 42», «дом 42», или просто короткое число
        if _HOUSE_TYPE_RE.search(lowered) or re.match(r"^\d+[а-яa-z]?(?:[/\-к]\d+)?$", part.strip()):
            if not result_house:
                result_house = _strip_house_prefix(part)
            continue

        # Микрорайон / квартал — НЕ улица, это часть локалити.
        # Игнорируем для целей поиска (rule.street не содержит мкр).
        if _DISTRICT_TYPE_RE.search(lowered):
            continue

        # Улица: маркер ул./пр-кт/шоссе/...
        # Если уже была улица — перезаписываем (последняя точнее, потому что
        # частые случаи «мкр X, ул Y» — но мкр мы уже отсекли выше).
        if _STREET_TYPE_RE.search(lowered):
            result_street = _strip_street_prefix(part)
            continue

        # Локалити: маркер г./город/...
        if _LOCALITY_TYPE_RE.search(lowered):
            if not result_locality:
                result_locality = _strip_locality_prefix(part)
            continue

        # Без маркера: первая «голая» часть после региона — населённый пункт,
        # вторая — улица. Грубо, но рабочее.
        if not result_locality:
            result_locality = part
        elif not result_street:
            result_street = part

    # Если улица не выделилась, но в локалити лежит «<имя> <число>»
    # (т.е. локалити по сути является «улица + дом»), переинтерпретируем.
    if not result_street and result_locality and re.search(r"\s+\d", result_locality):
        result_street = result_locality
        result_locality = ""

    # «Монастырская 96» в одной части — дом не отделён запятой.
    # Если в street остался хвост-число, отделим его в дом.
    if result_street and not result_house:
        m = re.search(r"\s+(\d+[а-яa-z]?(?:[/\-к]\d+)?)\s*$", result_street, re.IGNORECASE)
        if m:
            result_house = m.group(1)
            result_street = result_street[:m.start()].strip()

    return {
        "city": result_locality or None,
        "settlement": None,
        "street": result_street or None,
        "house": result_house or None,
        "result": address,
        "_source": "local_fallback",
    }
