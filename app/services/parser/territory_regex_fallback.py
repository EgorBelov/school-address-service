"""
Дешёвый regex-fallback для текста территории одной школы.

Запускается ПОСЛЕ LLM-парсера и добавляет правила, которые LLM
забыл / пропустил. Не претендует на 100% точность — но «грубое»
правило вида {street, house_rule_raw} лучше, чем потерянная улица.

Затем normalize_rule_fields() допилит типы/parity по тексту.
"""
import re


# Каждое вхождение — начало новой улицы.
# Маркер типа улицы + название (начинается с цифры или заглавной кириллицы).
# `finditer` найдёт ВСЕ улицы в тексте; интервал между двумя соседними
# матчами — описание домов для предыдущей улицы.
_STREET_RE = re.compile(
    r"(?:"
    r"улица|ул\.|"
    r"проспект|просп\.|пр-кт|пр-т|пр\.(?=\s+[А-ЯЁ])|"
    r"шоссе|ш\.(?=\s+[А-ЯЁ])|"
    r"бульвар|б-р|"
    r"переулок|пер\.|"
    r"проезд|пр-д|"
    r"набережная|наб\.|"
    r"площадь|пл\.(?=\s+[А-ЯЁ])|"
    r"тупик|туп\.|"
    r"аллея|линия|тракт"
    r")\s+"
    r"([\dА-ЯЁ][\dА-ЯЁа-яё\-\s\.]*?)"
    r"(?=,|\(|;|\.\s|\.$|$)",
    re.IGNORECASE,
)


_MKR_PREFIX_RE = re.compile(
    r"мкр\.?\s+[А-ЯЁа-яё\-\d ]+?\s*:", re.IGNORECASE
)


def extract_rules_from_territory_text(territory_text: str) -> list[dict]:
    """
    Возвращает список «сырых» правил: {street, house_rule_raw}.
    Поля house_from/house_to/parity потом проставит normalize_rule_fields.
    """
    if not territory_text:
        return []

    # Уберём префиксы «мкр. Балашиха-1:» — они не относятся к парсингу
    # отдельных улиц.
    text = _MKR_PREFIX_RE.sub(" ", territory_text)

    matches = list(_STREET_RE.finditer(text))
    rules: list[dict] = []

    for i, m in enumerate(matches):
        street = m.group(1).strip(" ,.-")
        if not street or len(street) < 2 or len(street) > 80:
            continue

        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        rest = text[m.end():next_start].strip(" ,;.").strip()

        rules.append({
            "locality": "",
            "street": street,
            "house_rule_raw": rest,
            "parity": None,
            "house_from": None,
            "house_to": None,
            "house_number": None,
            "comment": "",
        })

    return rules


def _norm_street_key(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.lower().strip().replace("ё", "е"))


def merge_llm_with_fallback(
    llm_rules: list[dict],
    fallback_rules: list[dict],
) -> list[dict]:
    """
    Объединяет правила от LLM с regex-fallback. Если улица уже есть
    в LLM-результате — не дублируем. Если в LLM пропущена — добавляем
    из fallback.
    """
    llm_streets = {_norm_street_key(r.get("street")) for r in llm_rules}

    merged = list(llm_rules)

    for rule in fallback_rules:
        key = _norm_street_key(rule.get("street"))
        if not key or key in llm_streets:
            continue

        merged.append(rule)
        llm_streets.add(key)

    return merged
