import json
from sqlalchemy.orm import Session

from app.models.models import Municipality, School, Decree, AddressRule
from app.services.dadata.street_validator import validate_street_with_dadata
from app.services.parser.rule_normalizer import normalize_rule_fields

def normalize_parity(value: str | None) -> str:
    if value in ["all", "even", "odd", "mixed", "unknown"]:
        return value
    return "unknown"


def normalize_house_number(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, list):
        return ",".join(str(item) for item in value)

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


_NUMBER_RE = __import__("re").compile(r"\d+")


def sanitize_school_address(value) -> str | None:
    """
    Адрес школы — это короткая строка с одним зданием
    («г. Балашиха, ул. Ленина, д. 21», максимум +«корп. 1»).
    Если LLM подсунул сюда фрагмент территории (список домов /
    несколько улиц) — отбрасываем.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if len(text) > 200:
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

    # Более 2 чисел = список домов: «Ленина, 10, 10а, 12»
    if nums_count > 2:
        return None

    # Если в строке 2+ чисел И нет явного маркера здания («д. 21», «корп.»)
    # И нет географической привязки — это территория, например «Объединения, 4, 6».
    import re as _re
    has_building = bool(_re.search(r"\bд\.\s*\d|\bкорп\.|\bстр\.", lowered))
    has_geo = bool(_re.search(r"\bг\.|город|посёлок|поселок|\bпос\.", lowered))

    if nums_count >= 2 and not has_building and not has_geo:
        return None

    return text


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


def save_parsed_decree(db: Session, parsed: dict) -> dict:
    decree_data = parsed.get("decree", {})
    schools_data = parsed.get("schools", [])

    municipality_name = decree_data.get("municipality") or "Неизвестный муниципалитет"

    municipality = db.query(Municipality).filter(
        Municipality.name == municipality_name
    ).first()

    if not municipality:
        municipality = Municipality(
            name=municipality_name,
            region="Пермский край"
        )
        db.add(municipality)
        db.flush()

    decree = Decree(
        municipality_id=municipality.id,
        number=decree_data.get("number") or "Без номера",
        date=decree_data.get("date") or "Без даты",
        file_path=None
    )
    db.add(decree)
    db.flush()

    schools_count = 0
    rules_count = 0

    for school_data in schools_data:
        school_name = school_data.get("name")

        if not school_name:
            continue

        school = db.query(School).filter(
            School.name == school_name,
            School.municipality_id == municipality.id
        ).first()

        if not school:
            school = School(
                municipality_id=municipality.id,
                name=school_name,
                address=sanitize_school_address(school_data.get("address")),
            )
            db.add(school)
            db.flush()

            schools_count += 1

        for rule_data in school_data.get("rules", []):
            
            rule_data = normalize_rule_fields(rule_data)
            
            street = rule_data.get("street")
            house_rule_raw = str(rule_data.get("house_rule_raw") or "").strip()
            house_number = rule_data.get("house_number")
            house_from = rule_data.get("house_from")
            house_to = rule_data.get("house_to")

            if not street:
                continue

            if not house_rule_raw and not house_number and not house_from and not house_to:
                continue
            
            locality = rule_data.get("locality")
            street_clean = street.replace("ул. ", "").replace("пр-кт ", "").strip()

            try:
                street_check = validate_street_with_dadata(
                    locality=locality,
                    street=street_clean,
                )
            except Exception as e:
                # DaData может тайм-аутиться или быть недоступна — не валим
                # всё сохранение, просто помечаем правило как непроверенное.
                print(f"[dadata] validation failed for {street_clean!r}: {e}")
                street_check = {
                    "status": "skipped",
                    "normalized_street": street_clean.lower(),
                    "dadata_value": None,
                    "confidence": None,
                    "comment": f"DaData недоступна: {e}",
                }

            rule = AddressRule(
                school_id=school.id,
                decree_id=decree.id,
                locality=locality,
                street=street_clean,
                normalized_street=street_check["normalized_street"],

                house_rule_raw=house_rule_raw,

                rule_type=normalize_rule_type(rule_data.get("rule_type")),
                parity=normalize_parity(rule_data.get("parity")),

                house_from=normalize_int(rule_data.get("house_from")),
                house_to=normalize_int(rule_data.get("house_to")),
                house_number=normalize_house_number(rule_data.get("house_number")),
                house_numbers=normalize_list(rule_data.get("house_numbers")),
                exceptions=normalize_list(rule_data.get("exceptions")),

                comment=rule_data.get("comment"),

                dadata_value=street_check["dadata_value"],
                dadata_confidence=street_check["confidence"],
                validation_status=street_check["status"],
                validation_comment=street_check["comment"],
            )

            db.add(rule)
            rules_count += 1

    db.commit()

    return {
        "municipality": municipality.name,
        "decree_id": decree.id,
        "schools_count": schools_count,
        "rules_count": rules_count
    }

def normalize_list(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())

    return str(value).strip() or None


def normalize_rule_type(value: str | None) -> str:
    allowed = [
        "all",
        "exact_list",
        "range",
        "up_to",
        "from_to_end",
        "all_except",
        "intersection_segment",
        "mixed",
        "unknown",
    ]

    if value in allowed:
        return value

    return "unknown"