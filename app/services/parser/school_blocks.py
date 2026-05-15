import re


SCHOOL_QUOTE_RE = re.compile(
    r"«[^»]*(?:школа|гимназия|лицей)[^»]*»",
    re.IGNORECASE | re.DOTALL,
)

TERRITORY_RE = re.compile(
    r"(мкр\.|ул\.|проспект|шоссе|площадь|квартал|СНТ|ДПК|ЖК|д\.|с\.|п\.)",
    re.IGNORECASE,
)


def clean_text(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = text.replace("\xa0", " ")
    return text


def extract_full_school_name(text: str, quote_match: re.Match) -> str:
    start = max(0, quote_match.start() - 250)
    prefix = text[start:quote_match.start()]
    quote = text[quote_match.start():quote_match.end()]

    # Берём кусок перед кавычками, где обычно:
    # Муниципальное бюджетное общеобразовательное учреждение...
    prefix_lines = prefix.splitlines()

    useful_lines = []
    for line in reversed(prefix_lines):
        line_clean = clean_text(line)

        if not line_clean:
            continue

        if TERRITORY_RE.search(line_clean):
            break

        useful_lines.insert(0, line_clean)

        if "Муниципальное" in line_clean:
            break

    full_name = clean_text(" ".join(useful_lines + [quote]))
    return full_name


def extract_school_blocks(text: str) -> list[dict]:
    text = normalize_text(text)

    matches = list(SCHOOL_QUOTE_RE.finditer(text))
    blocks = []

    print(f"[school_blocks] found school quotes: {len(matches)}")

    for i, match in enumerate(matches):
        school_name = extract_full_school_name(text, match)

        territory_start = match.end()
        territory_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        territory_candidate = text[territory_start:territory_end]
        territory_match = TERRITORY_RE.search(territory_candidate)

        if not territory_match:
            print("[school_blocks] no territory:", school_name)
            continue

        territory_text = clean_text(
            territory_candidate[territory_match.start():]
        )

        if len(school_name) < 10 or len(territory_text) < 10:
            continue

        blocks.append({
            "school_name": school_name,
            "territory_text": territory_text,
        })

    print(f"[school_blocks] parsed blocks: {len(blocks)}")

    return blocks