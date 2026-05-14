import re


def normalize_street_name(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower().strip()

    replacements = [
        "улица",
        "ул.",
        "ул",
        "проспект",
        "пр-кт",
        "пр.",
        "пер.",
        "пер",
        "переулок",
        "проезд",
        "пр-д",
        "бульвар",
        "б-р",
    ]

    for item in replacements:
        value = value.replace(item, "")

    value = re.sub(r"\s+", " ", value)
    return value.strip()