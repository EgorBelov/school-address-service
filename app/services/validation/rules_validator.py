from sqlalchemy.orm import Session

from app.models.models import AddressRule
from app.services.address.normalize import normalize_street_name


def validate_rules(db: Session) -> list[dict]:
    issues = []

    rules = db.query(AddressRule).all()

    for rule in rules:
        if not rule.street or not rule.street.strip():
            issues.append({
                "level": "error",
                "type": "empty_street",
                "message": "У правила не указана улица",
                "rule_id": rule.id,
                "school": rule.school.name if rule.school else "—",
            })

        if not rule.house_rule_raw or not rule.house_rule_raw.strip():
            issues.append({
                "level": "warning",
                "type": "empty_house_rule",
                "message": "У правила пустое описание домов",
                "rule_id": rule.id,
                "school": rule.school.name if rule.school else "—",
            })

        if rule.house_from and rule.house_to and rule.house_from > rule.house_to:
            issues.append({
                "level": "error",
                "type": "invalid_range",
                "message": f"Некорректный диапазон: {rule.house_from}–{rule.house_to}",
                "rule_id": rule.id,
                "school": rule.school.name if rule.school else "—",
            })

        if rule.parity not in ["all", "even", "odd", "mixed", "unknown"]:
            issues.append({
                "level": "warning",
                "type": "unknown_parity",
                "message": f"Неизвестная чётность: {rule.parity}",
                "rule_id": rule.id,
                "school": rule.school.name if rule.school else "—",
            })

    issues.extend(find_intersections(rules))

    return issues


def rule_to_numbers(rule: AddressRule, limit: int = 300) -> set[int]:
    raw = (rule.house_rule_raw or "").lower()

    if raw in ["все", "все дома"]:
        return set(range(1, limit + 1))

    numbers = set()

    if rule.house_number:
        for item in str(rule.house_number).split(","):
            item = item.strip()
            if item.isdigit():
                numbers.add(int(item))

    if rule.house_from is not None and rule.house_to is not None:
        for number in range(rule.house_from, rule.house_to + 1):
            if rule.parity == "even" and number % 2 != 0:
                continue
            if rule.parity == "odd" and number % 2 == 0:
                continue
            numbers.add(number)

    return numbers


def find_intersections(rules: list[AddressRule]) -> list[dict]:
    issues = []

    grouped = {}

    for rule in rules:
        street = normalize_street_name(rule.street)
        locality = (rule.locality or "").lower().strip()
        key = f"{locality}:{street}"

        grouped.setdefault(key, []).append(rule)

    for _, group in grouped.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                rule_a = group[i]
                rule_b = group[j]

                if rule_a.school_id == rule_b.school_id:
                    continue

                nums_a = rule_to_numbers(rule_a)
                nums_b = rule_to_numbers(rule_b)

                intersection = nums_a & nums_b

                if intersection:
                    preview = sorted(list(intersection))[:10]

                    issues.append({
                        "level": "error",
                        "type": "intersection",
                        "message": (
                            f"Пересечение правил по улице {rule_a.street}: "
                            f"дома {preview}"
                        ),
                        "rule_id": rule_a.id,
                        "second_rule_id": rule_b.id,
                        "school": rule_a.school.name if rule_a.school else "—",
                        "second_school": rule_b.school.name if rule_b.school else "—",
                    })

    return issues