import json
import re
import time
from pathlib import Path

from pydantic import ValidationError

from app.services.ai.gigachat.client import get_gigachat_client
from app.services.ai.gigachat.decree_parser import (
    _INTER_REQUEST_DELAY,
    _is_transient_error,
    _MAX_RETRIES,
    _RETRY_BASE_DELAY,
    parse_decree_with_gigachat,
)
from app.services.ai.gigachat.schemas import TerritoryResponseModel
from app.services.parser.docx_table_extractor import extract_school_table_rows_from_docx
from app.services.parser.metadata_extractor import extract_decree_metadata
from app.services.parser.pdf_table_extractor import extract_school_table_rows_from_pdf
from app.services.parser.strategies.base import BaseParserStrategy
from app.services.parser.territory_regex_fallback import (
    extract_rules_from_territory_text,
    merge_llm_with_fallback,
)
from app.services.parser.text_extractor import convert_doc_to_docx


TERRITORY_ONLY_PROMPT = """
Ты парсишь ТОЛЬКО список территорий, закрепленных за одной школой.

Название школы уже известно отдельно. Не придумывай школу.

Верни строго JSON без markdown.

Формат:

{
  "rules": [
    {
      "locality": "",
      "street": "",
      "house_rule_raw": "",
      "parity": "all|even|odd|mixed|unknown",
      "house_from": null,
      "house_to": null,
      "house_number": null,
      "comment": ""
    }
  ]
}

Правила извлечения:
- В street НЕ включай "ул.", "пр-кт", "переулок", "шоссе" — только название улицы.
- "все" / пусто => parity="all", диапазоны null.
- "четные дома" => parity="even".
- "нечетные дома" => parity="odd".
- house_number — список конкретных домов через запятую (строкой), например "10,10а,12".
- Сложное условие ("кроме д.11") сохраняй в comment.
- Не возвращай пустые street.

Примеры:

"ул. Заречная (четные и нечетные до дома 18)" =>
{"street":"Заречная","house_rule_raw":"(четные и нечетные до дома 18)","parity":"all","house_from":null,"house_to":18,"house_number":null,"comment":""}

"проспект Ленина, 10, 10а, 12, 14" =>
{"street":"Ленина","house_rule_raw":"10, 10а, 12, 14","parity":"all","house_from":null,"house_to":null,"house_number":"10,10а,12,14","comment":""}

"ул. Молодежная (кроме д.11)" =>
{"street":"Молодежная","house_rule_raw":"(кроме д.11)","parity":"all","house_from":null,"house_to":null,"house_number":null,"comment":"кроме д.11"}

"ул. Новая (начиная с дома 36)" =>
{"street":"Новая","house_rule_raw":"(начиная с дома 36)","parity":"all","house_from":36,"house_to":null,"house_number":null,"comment":""}

"ул. 40 лет Победы, 1-17" =>
{"street":"40 лет Победы","house_rule_raw":"1-17","parity":"all","house_from":1,"house_to":17,"house_number":null,"comment":""}

"Щелковское шоссе (четные – от дома 102, нечетные – от дома 141)" =>
два отдельных правила: одно с parity="even" house_from=102, второе с parity="odd" house_from=141.

Текст территорий:

{text}
"""


def extract_table_rows_for_file(file_path: str) -> list[dict]:
    """
    Диспетчер по расширению файла. Возвращает список
    {school_name, territory_text, page} — общий формат для PDF и DOCX.
    """
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        return extract_school_table_rows_from_pdf(file_path)

    if suffix == ".docx":
        return extract_school_table_rows_from_docx(file_path)

    if suffix == ".doc":
        converted = convert_doc_to_docx(file_path)
        if converted:
            return extract_school_table_rows_from_docx(converted)
        return []

    return []


def parse_territory_response(content: str) -> dict:
    """JSON → Pydantic-валидация → dict с правильными типами."""
    cleaned = content.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if not match:
        raise ValueError("GigaChat не вернул JSON")

    cleaned = match.group(0)
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Невалидный JSON: {e}")

    try:
        validated = TerritoryResponseModel.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Не соответствует схеме TerritoryResponseModel:\n{e}")

    return validated.model_dump()


class TwoColumnParserStrategy(BaseParserStrategy):
    def parse(self, text: str, file_path: str | None = None) -> dict:
        client = get_gigachat_client()

        rows: list[dict] = []
        if file_path:
            rows = extract_table_rows_for_file(file_path)

        # Метаданные сразу регэкспом — дёшево, не зависит от LLM
        metadata = extract_decree_metadata(text)

        result = {
            "decree": {
                "number": metadata["number"],
                "date": metadata["date"],
                "municipality": metadata["municipality"] or "городской округ Балашиха",
            },
            "schools": [],
            "errors": [],
        }

        if not rows:
            # Fallback: документ без распознаваемых таблиц.
            # Парсим сырой текст обычным многошкольным парсером.
            print("[two_column] no tables found, falling back to plain-text LLM parser")

            fallback = parse_decree_with_gigachat(text)

            # Если LLM не заполнил поля — берём наши регэксповые / дефолтные
            decree = fallback.get("decree", {}) or {}
            for key, value in result["decree"].items():
                if value and not decree.get(key):
                    decree[key] = value
            fallback["decree"] = decree

            fallback.setdefault("errors", []).append({
                "info": "fallback_to_plain_text",
                "reason": "Не удалось извлечь таблицы — обработали как обычный текст.",
            })

            return fallback

        for index, row in enumerate(rows, start=1):
            if index > 1:
                time.sleep(_INTER_REQUEST_DELAY)

            territory_text = row["territory_text"]
            fallback_rules = extract_rules_from_territory_text(territory_text)

            try:
                parsed = _call_llm_for_territory_with_retry(
                    client, territory_text[:3500]
                )
                llm_rules = parsed.get("rules", []) or []
            except Exception as e:
                result["errors"].append({
                    "row": index,
                    "page": row.get("page"),
                    "school_name": row.get("school_name"),
                    "error": str(e),
                    "preview": territory_text[:500],
                })
                llm_rules = []

            # Доклеиваем regex-fallback к ответу LLM: те улицы, которые
            # LLM пропустил, не теряются — попадают «сырыми» правилами,
            # дальше их доразберёт normalize_rule_fields() при сохранении.
            merged = merge_llm_with_fallback(llm_rules, fallback_rules)

            result["schools"].append({
                "name": row["school_name"],
                "address": "",
                "rules": merged,
            })

        return result


def _call_llm_for_territory_with_retry(client, territory_text: str) -> dict:
    """Один LLM-запрос на территорию одной школы, с retry на 429 / timeout."""
    prompt = TERRITORY_ONLY_PROMPT.replace("{text}", territory_text)

    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = client.chat(prompt)
            return parse_territory_response(response.choices[0].message.content)
        except Exception as e:
            last_error = e

            if not _is_transient_error(e) or attempt == _MAX_RETRIES:
                raise

            wait = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            print(
                f"[gigachat] territory transient error on attempt {attempt}: {e}"
                f" → retry in {wait:.0f}s"
            )
            time.sleep(wait)

    raise last_error if last_error else RuntimeError("unreachable")
