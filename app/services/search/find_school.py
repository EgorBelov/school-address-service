"""
Поиск школы по адресу.

Алгоритм:
  1. Нормализуем введённую улицу и локалити.
  2. Линейно идём по всем правилам (учебный масштаб — ~700 строк, ок).
  3. Для каждого правила: сравниваем улицу → локалити → дом.

Используем `rule.street` (исходное название), а не `normalized_street`
от DaData: DaData иногда нормализует «шоссе Космонавтов» в случайный
ГСК по соседству, и поиск ломается.
"""
import re

from sqlalchemy.orm import Session

from app.models.models import AddressRule
from app.services.address.normalize import normalize_locality, normalize_street_name


# ───────────────────────── Дом ─────────────────────────

def _house_number(house: str | None) -> int | None:
    """«42а» → 42, «12/3» → 12, «отсутствует» → None."""
    if not house:
        return None
    match = re.search(r"\d+", str(house))
    return int(match.group()) if match else None


def _normalize_house(value: str | None) -> str:
    if not value:
        return ""
    return str(value).lower().replace(" ", "").strip()


def _parse_number_list(value: str | None) -> set[str]:
    """«1, 2, 5а» → {'1', '2', '5а'}."""
    if not value:
        return set()
    return {
        _normalize_house(item)
        for item in str(value).split(",")
        if item.strip()
    }


def is_house_matches(rule: AddressRule, house: str | None) -> bool:
    """Проверяет, попадает ли дом под правило."""
    number = _house_number(house)
    target = _normalize_house(house)

    raw = (rule.house_rule_raw or "").lower().strip()
    rule_type = rule.rule_type or "unknown"

    if target in _parse_number_list(rule.exceptions):
        return False

    if raw in ("все", "все дома") or rule_type == "all":
        return True

    exact = _parse_number_list(rule.house_numbers) | _parse_number_list(rule.house_number)
    if target in exact:
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


# ───────────────────────── Населённый пункт ─────────────────────────

def _locality_key(value: str) -> str:
    return normalize_locality(value).replace("ё", "е")


def _locality_match(a: str, b: str) -> bool:
    """
    Толерантное сравнение двух локали — учитывает падеж и букву «ё»:
      «Пермь» / «Перми» → match
      «Берёзники» / «Березников» → match
      «Балашиха» / «Балашихи» → match
      «Балашиха» / «Балахна» → mismatch

    Общий префикс ≥4 символа; различие в последних 1–2 символах
    (типичные падежные окончания) считается совпадением.
    """
    a = _locality_key(a)
    b = _locality_key(b)
    if not a or not b:
        return False
    if a == b:
        return True

    common = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        common += 1

    if common < 4:
        return False

    return (len(a) - common) <= 2 and (len(b) - common) <= 2


def is_locality_matches(rule: AddressRule, target_locality: str) -> bool:
    """
    Применимо ли правило к адресу с указанным населённым пунктом.
    Сравниваем target с двумя источниками — `rule.locality` и
    `school.municipality.name`. Если оба пусты — фильтр пропускаем
    (best effort, иногда правило не привязано к локалити).
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

    return any(_locality_match(c, target_locality) for c in candidates)


# ───────────────────────── Поиск ─────────────────────────

def find_school_by_address(
    db: Session,
    locality: str | None,
    street: str,
    house: str | None,
) -> dict | None:
    target_street = normalize_street_name(street)
    target_locality = normalize_locality(locality)

    for rule in db.query(AddressRule).all():
        if normalize_street_name(rule.street) != target_street:
            continue
        if not is_locality_matches(rule, target_locality):
            continue
        if is_house_matches(rule, house):
            return {"school": rule.school, "rule": rule}

    return None
