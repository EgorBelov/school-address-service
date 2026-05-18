import re
from sqlalchemy.orm import Session

from app.models.models import AddressRule
from app.services.address.normalize import normalize_locality, normalize_street_name


def extract_house_number(house: str | None) -> int | None:
    if not house:
        return None

    match = re.search(r"\d+", str(house))
    return int(match.group()) if match else None


def normalize_house(value: str | None) -> str:
    if not value:
        return ""

    return str(value).lower().replace(" ", "").strip()


def house_in_list(rule_house_number: str | None, house: str | None) -> bool:
    if not rule_house_number or not house:
        return False

    target = normalize_house(house)

    items = [
        normalize_house(item)
        for item in str(rule_house_number).split(",")
        if item.strip()
    ]

    return target in items


def parse_number_list(value: str | None) -> set[str]:
    if not value:
        return set()

    return {
        normalize_house(item)
        for item in str(value).split(",")
        if item.strip()
    }


def is_house_matches(rule: AddressRule, house: str | None) -> bool:
    number = extract_house_number(house)
    target_house = normalize_house(house)

    raw = (rule.house_rule_raw or "").lower().strip()
    rule_type = rule.rule_type or "unknown"

    exceptions = parse_number_list(rule.exceptions)

    if target_house in exceptions:
        return False

    if raw in ["все", "все дома"] or rule_type == "all":
        return True

    exact_numbers = parse_number_list(rule.house_numbers) | parse_number_list(rule.house_number)

    if target_house in exact_numbers:
        return True

    if number is None:
        return False

    if rule.parity == "even" and number % 2 != 0:
        return False

    if rule.parity == "odd" and number % 2 == 0:
        return False

    if rule_type == "up_to" and rule.house_to is not None:
        return number <= rule.house_to

    if rule_type == "from_to_end" and rule.house_from is not None:
        return number >= rule.house_from

    if rule.house_from is not None and rule.house_to is not None:
        return rule.house_from <= number <= rule.house_to

    return False


def _locality_key(value: str) -> str:
    """Нормализованная форма локали (lowercase, ё→е, без типа поселения)."""
    return normalize_locality(value).replace("ё", "е")


def _locality_match(a: str, b: str) -> bool:
    """
    Толерантное сравнение двух локали — учитывает падеж и букву «ё»:
      «Пермь» / «Перми» → match
      «Берёзники» / «Березников» → match
      «Балашиха» / «Балашихи» → match
      «Балашиха» / «Балахна» → mismatch
    Алгоритм: ищем общий префикс ≥4 символа; различие в последних
    1–2 символах (типичные падежные окончания) считается совпадением.
    """
    a = _locality_key(a)
    b = _locality_key(b)
    if not a or not b:
        return False
    if a == b:
        return True

    common = 0
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            break
        common += 1

    if common < 4:
        return False

    tail_a = len(a) - common
    tail_b = len(b) - common
    return tail_a <= 2 and tail_b <= 2


def is_locality_matches(rule: AddressRule, target_locality: str) -> bool:
    """
    Правило применимо к адресу, только если совпадает населённый пункт.
    Берём два источника (что заполнено — то и сравниваем):
      1. rule.locality — locality из самого правила;
      2. rule.school.municipality.name — муниципалитет школы.
    Если у правила ни один источник не заполнен — пропускаем фильтр
    (best effort). Если target_locality пустой — тоже не отсеиваем.
    """
    if not target_locality:
        return True

    candidates: list[str] = []

    if rule.locality:
        candidates.append(rule.locality)

    school = getattr(rule, "school", None)
    if school is not None:
        municipality = getattr(school, "municipality", None)
        if municipality is not None and municipality.name:
            candidates.append(municipality.name)

    if not candidates:
        return True

    for candidate in candidates:
        if _locality_match(candidate, target_locality):
            return True

    return False


def find_school_by_address(
    db: Session,
    locality: str | None,
    street: str,
    house: str | None
):
    target_street = normalize_street_name(street)
    target_locality = normalize_locality(locality)

    rules = db.query(AddressRule).all()

    for rule in rules:
        # Используем ИСХОДНЫЙ rule.street из постановления, а НЕ
        # `normalized_street` от DaData — последний часто содержит
        # мусор (привязка к ГСК / гаражному кооперативу / другому
        # объекту по соседству), что ломает поиск по улице.
        rule_street = normalize_street_name(rule.street)

        if rule_street != target_street:
            continue

        if not is_locality_matches(rule, target_locality):
            continue

        if is_house_matches(rule, house):
            return {
                "school": rule.school,
                "rule": rule,
            }

    return None