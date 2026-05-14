import json
from sqlalchemy.orm import Session

from app.models.models import Municipality, School, Decree, AddressRule


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
                address=school_data.get("address")
            )
            db.add(school)
            db.flush()

            schools_count += 1

        for rule_data in school_data.get("rules", []):
            street = rule_data.get("street")
            house_rule_raw = str(rule_data.get("house_rule_raw") or "").strip()
            house_number = rule_data.get("house_number")
            house_from = rule_data.get("house_from")
            house_to = rule_data.get("house_to")

            if not street:
                continue

            if not house_rule_raw and not house_number and not house_from and not house_to:
                continue

            rule = AddressRule(
                school_id=school.id,
                decree_id=decree.id,
                locality=rule_data.get("locality"),
                street=street.replace("ул. ", "").replace("пр-кт ", "").strip(),
                house_rule_raw=house_rule_raw,
                parity=normalize_parity(rule_data.get("parity")),
                house_from=normalize_int(rule_data.get("house_from")),
                house_to=normalize_int(rule_data.get("house_to")),
                house_number=normalize_house_number(rule_data.get("house_number")),
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