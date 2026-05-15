import re
from sqlalchemy.orm import Session

from app.models.models import AddressRule
from app.services.address.normalize import normalize_street_name


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


def find_school_by_address(
    db: Session,
    locality: str | None,
    street: str,
    house: str | None
):
    target_street = normalize_street_name(street)

    rules = db.query(AddressRule).all()

    for rule in rules:
        rule_street = normalize_street_name(rule.normalized_street or rule.street)

        if rule_street != target_street:
            continue

        if is_house_matches(rule, house):
            return {
                "school": rule.school,
                "rule": rule,
            }

    return None