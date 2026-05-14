import re


def split_text_by_schools(text: str) -> list[str]:
    """
    Делит постановление на блоки по школам.
    Работает по строкам, где начинается новая школа:
    1.
    2.
    4.1.
    11.2.
    """

    pattern = re.compile(
        r"\n\s*(\d+(?:\.\d+)?\.)\s*\n",
        re.MULTILINE
    )

    matches = list(pattern.finditer(text))

    if not matches:
        return split_text_by_size(text)

    chunks = []

    for index, match in enumerate(matches):
        start = match.start()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        chunk = text[start:end].strip()

        if len(chunk) > 300:
            chunks.append(chunk)

    return chunks


def split_text_by_size(text: str, max_size: int = 4000) -> list[str]:
    chunks = []

    for i in range(0, len(text), max_size):
        chunk = text[i:i + max_size].strip()

        if chunk:
            chunks.append(chunk)

    return chunks