"""
Сохранение распарсенного постановления в БД.

На вход — структура от парсеров (двухколоночного/многоколоночного/LLM):
    {
        "decree": {"number": "", "date": "", "municipality": ""},
        "schools": [{"name": "", "address": "", "rules": [...]}]
    }
"""
import json
import re

from sqlalchemy.orm import Session

from app.models.models import AddressRule, Decree, Municipality, School
from app.services.address.normalize import normalize_street_name
from app.services.dadata.street_validator import validate_street_with_dadata
from app.services.parser.rule_normalizer import normalize_rule_fields


# ───────────────────────── Нормализаторы значений ─────────────────────────

_ALLOWED_PARITY = {"all", "even", "odd", "mixed", "unknown"}

_ALLOWED_RULE_TYPE = {
    "all", "exact_list", "range",
    "up_to", "from_to_end", "all_except",
    "intersection_segment", "mixed", "unknown",
}

_NUMBER_RE = re.compile(r"\d+")
_BUILDING_MARKER_RE = re.compile(r"\bд\.\s*\d|\bкорп\.|\bстр\.", re.IGNORECASE)
_GEO_MARKER_RE = re.compile(r"\bг\.|город|посёлок|поселок|\bпос\.", re.IGNORECASE)


def normalize_parity(value: str | None) -> str:
    return value if value in _ALLOWED_PARITY else "unknown"


def normalize_rule_type(value: str | None) -> str:
    return value if value in _ALLOWED_RULE_TYPE else "unknown"


def normalize_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return int(value)
    return None


def normalize_house_number(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        joined = ",".join(str(item) for item in value if str(item).strip())
        return joined or None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    return text or None


def normalize_list(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        joined = ",".join(str(item).strip() for item in value if str(item).strip())
        return joined or None
    return str(value).strip() or None


def sanitize_school_address(value) -> str | None:
    """
    Адрес школы — короткая строка одного здания. Если LLM подсунул
    сюда фрагмент территории (список домов / несколько улиц) —
    отбрасываем, иначе в UI будут «адреса школ» вроде «ул. Объединения, 4, 6».
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text or len(text) > 200:
        return None

    lowered = text.lower()

    # Несколько разделителей улиц / точек с запятой = территория
    if (
        text.count(";") >= 1
        or lowered.count("ул.") >= 2
        or lowered.count("мкр.") >= 1
    ):
        return None

    nums_count = len(_NUMBER_RE.findall(text))

    # Более 2 чисел = список домов
    if nums_count > 2:
        return None

    # 2 числа без признаков здания/города — тоже территория
    has_building = bool(_BUILDING_MARKER_RE.search(lowered))
    has_geo = bool(_GEO_MARKER_RE.search(lowered))
    if nums_count >= 2 and not has_building and not has_geo:
        return None

    return text


def _clean_street(street: str) -> str:
    """Убираем у name улицы избыточный префикс типа («ул. », «пр-кт »)."""
    return street.replace("ул. ", "").replace("пр-кт ", "").strip()


def _safe_dadata_check(locality: str | None, street: str) -> dict:
    """DaData может тайм-аутиться — оборачиваем в try/except."""
    try:
        return validate_street_with_dadata(locality=locality, street=street)
    except Exception as e:
        print(f"[dadata] validation failed for {street!r}: {e}")
        return {
            "status": "skipped",
            "normalized_street": normalize_street_name(street),
            "dadata_value": None,
            "confidence": None,
            "comment": f"DaData недоступна: {e}",
        }


# ───────────────────────── Основная функция ─────────────────────────

def _get_or_create_municipality(db: Session, name: str) -> Municipality:
    municipality = (
        db.query(Municipality).filter(Municipality.name == name).first()
    )
    if municipality:
        return municipality

    municipality = Municipality(name=name, region=None)
    db.add(municipality)
    db.flush()
    return municipality


def _get_or_create_school(
    db: Session, municipality_id: int, name: str, address: str | None
) -> tuple[School, bool]:
    """Возвращает (school, created)."""
    school = (
        db.query(School)
        .filter(School.name == name, School.municipality_id == municipality_id)
        .first()
    )
    if school:
        return school, False

    school = School(
        municipality_id=municipality_id,
        name=name,
        address=sanitize_school_address(address),
    )
    db.add(school)
    db.flush()
    return school, True


def _build_rule(
    school_id: int,
    decree_id: int,
    rule_data: dict,
) -> AddressRule | None:
    """Превращает «сырое» правило в ORM-объект или None если оно невалидно."""
    rule_data = normalize_rule_fields(rule_data)

    street = (rule_data.get("street") or "").strip()
    if not street:
        return None

    house_rule_raw = str(rule_data.get("house_rule_raw") or "").strip()
    house_number = rule_data.get("house_number")
    house_from = rule_data.get("house_from")
    house_to = rule_data.get("house_to")

    # Пустое правило (без описания домов и без диапазона) сохраняем только
    # если rule_type == "all" — иначе это бесполезная запись.
    if (
        not house_rule_raw
        and not house_number
        and not house_from
        and not house_to
        and rule_data.get("rule_type") != "all"
    ):
        return None

    street_clean = _clean_street(street)
    locality = rule_data.get("locality")
    dadata = _safe_dadata_check(locality, street_clean)

    return AddressRule(
        school_id=school_id,
        decree_id=decree_id,
        locality=locality,
        street=street_clean,
        normalized_street=normalize_street_name(street_clean),
        house_rule_raw=house_rule_raw,
        rule_type=normalize_rule_type(rule_data.get("rule_type")),
        parity=normalize_parity(rule_data.get("parity")),
        house_from=normalize_int(house_from),
        house_to=normalize_int(house_to),
        house_number=normalize_house_number(house_number),
        house_numbers=normalize_list(rule_data.get("house_numbers")),
        exceptions=normalize_list(rule_data.get("exceptions")),
        comment=rule_data.get("comment"),
        dadata_value=dadata["dadata_value"],
        dadata_confidence=dadata["confidence"],
        validation_status=dadata["status"],
        validation_comment=dadata["comment"],
    )


def save_parsed_decree(db: Session, parsed: dict) -> dict:
    decree_data = parsed.get("decree") or {}
    schools_data = parsed.get("schools") or []

    municipality_name = decree_data.get("municipality") or "Неизвестный муниципалитет"
    municipality = _get_or_create_municipality(db, municipality_name)

    decree = Decree(
        municipality_id=municipality.id,
        number=decree_data.get("number") or "Без номера",
        date=decree_data.get("date") or "Без даты",
        file_path=None,
    )
    db.add(decree)
    db.flush()

    schools_count = 0
    rules_count = 0

    for school_data in schools_data:
        name = (school_data.get("name") or "").strip()
        if not name:
            continue

        school, created = _get_or_create_school(
            db, municipality.id, name, school_data.get("address")
        )
        if created:
            schools_count += 1

        for rule_data in school_data.get("rules") or []:
            rule = _build_rule(school.id, decree.id, rule_data)
            if rule is None:
                continue
            db.add(rule)
            rules_count += 1

    db.commit()

    return {
        "municipality": municipality.name,
        "decree_id": decree.id,
        "schools_count": schools_count,
        "rules_count": rules_count,
    }
