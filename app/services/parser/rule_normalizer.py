import re


def parse_house_tokens(raw: str) -> list[str]:
    return re.findall(r"\d+[а-яА-Яa-zA-Z]?(?:/\d+)?", raw)


def normalize_rule_fields(rule_data: dict) -> dict:
    raw = str(rule_data.get("house_rule_raw") or "").lower()

    # "начиная с дома 36", "от дома 20"
    from_match = re.search(r"(начиная с|от дома|от)\s*(?:дома|д\.)?\s*(\d+)", raw)
    if from_match:
        rule_data["rule_type"] = "from_to_end"
        rule_data["house_from"] = int(from_match.group(2))
        rule_data["house_to"] = None
        return rule_data

    # "до дома 18"
    to_match = re.search(r"до\s*(?:дома|д\.)?\s*(\d+)", raw)
    if to_match:
        rule_data["rule_type"] = "up_to"
        rule_data["house_from"] = None
        rule_data["house_to"] = int(to_match.group(1))
        return rule_data

    # "кроме д.11"
    except_items = re.findall(r"кроме\s*(?:домов|дома|д\.)?\s*([\d,\sа-яА-Яa-zA-Z/]+)", raw)
    if except_items:
        nums = []
        for item in except_items:
            nums.extend(parse_house_tokens(item))

        rule_data["rule_type"] = "all_except"
        rule_data["exceptions"] = nums
        return rule_data

    # "10, 10а, 12, 14" — список конкретных домов
    tokens = parse_house_tokens(raw)
    if tokens and "," in raw:
        rule_data["rule_type"] = "exact_list"
        rule_data["house_numbers"] = tokens
        rule_data["house_from"] = None
        rule_data["house_to"] = None
        return rule_data

    # "1-17", "32 - 66"
    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", raw)
    if range_match:
        rule_data["rule_type"] = "range"
        rule_data["house_from"] = int(range_match.group(1))
        rule_data["house_to"] = int(range_match.group(2))
        return rule_data

    if raw in ["все", "все дома"] or not raw:
        rule_data["rule_type"] = "all"

    return rule_data