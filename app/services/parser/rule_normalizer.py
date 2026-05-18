import re


def parse_house_tokens(raw: str) -> list[str]:
    return re.findall(r"\d+[а-яА-Яa-zA-Z]?(?:/\d+)?", raw)


def detect_parity(raw: str) -> str | None:
    """
    Определяет чётность по тексту правила. Возвращает None, если
    явных маркеров нет (тогда оставляем то, что прислал LLM).

    Внимание: «чет» — это подстрока «нечет», поэтому сначала ищем
    «нечет» и убираем его, и только потом проверяем «чет».
    """
    lowered = raw.lower()

    has_odd = "нечет" in lowered or "нечёт" in lowered

    # Вырезаем «нечет/нечёт» — оставшиеся «чет/чёт» это уже чётные.
    cleaned = re.sub(r"неч[её]т", "", lowered)
    has_even = "чет" in cleaned or "чёт" in cleaned

    if has_odd and has_even:
        return "all"
    if has_odd:
        return "odd"
    if has_even:
        return "even"
    return None


def normalize_rule_fields(rule_data: dict) -> dict:
    raw = str(rule_data.get("house_rule_raw") or "").lower()

    # Сначала определяем чётность независимо — её надо проставить даже
    # если потом сработает range/from_to_end/up_to.
    parity = detect_parity(raw)
    if parity and not rule_data.get("parity"):
        rule_data["parity"] = parity
    elif parity and rule_data.get("parity") in (None, "", "unknown"):
        rule_data["parity"] = parity
    # если LLM явно сказал "all"/"even"/"odd" — не перезатираем

    # "начиная с дома 36", "от дома 20"
    from_match = re.search(r"(начиная с|от дома|от)\s*(?:дома|д\.)?\s*(\d+)", raw)
    if from_match:
        rule_data["rule_type"] = "from_to_end"
        rule_data["house_from"] = int(from_match.group(2))
        rule_data["house_to"] = None
        if parity and rule_data.get("parity") in (None, "", "unknown", "all"):
            rule_data["parity"] = parity
        return rule_data

    # "до дома 18"
    to_match = re.search(r"до\s*(?:дома|д\.)?\s*(\d+)", raw)
    if to_match:
        rule_data["rule_type"] = "up_to"
        rule_data["house_from"] = None
        rule_data["house_to"] = int(to_match.group(1))
        if parity and rule_data.get("parity") in (None, "", "unknown", "all"):
            rule_data["parity"] = parity
        return rule_data

    # "кроме д.11"
    except_items = re.findall(
        r"кроме\s*(?:домов|дома|д\.)?\s*([\d,\sа-яА-Яa-zA-Z/]+)", raw
    )
    if except_items:
        nums = []
        for item in except_items:
            nums.extend(parse_house_tokens(item))

        rule_data["rule_type"] = "all_except"
        rule_data["exceptions"] = nums
        return rule_data

    # "1-17", "32 - 66", "45 – 85" — диапазон (проверяем до exact_list,
    # т.к. exact_list тоже сматчит числа, но без признака диапазона).
    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", raw)
    if range_match:
        rule_data["rule_type"] = "range"
        rule_data["house_from"] = int(range_match.group(1))
        rule_data["house_to"] = int(range_match.group(2))
        if parity and rule_data.get("parity") in (None, "", "unknown", "all"):
            rule_data["parity"] = parity
        return rule_data

    # "10, 10а, 12, 14" — список конкретных домов
    tokens = parse_house_tokens(raw)
    if tokens and "," in raw:
        rule_data["rule_type"] = "exact_list"
        rule_data["house_numbers"] = tokens
        rule_data["house_from"] = None
        rule_data["house_to"] = None
        return rule_data

    if raw in ["все", "все дома"] or not raw:
        rule_data["rule_type"] = "all"

    return rule_data
