import json
import re

from pydantic import ValidationError

from app.services.ai.gigachat.client import get_gigachat_client
from app.services.ai.gigachat.prompts import DECREE_PARSE_PROMPT
from app.services.ai.gigachat.schemas import DecreeResponseModel
from app.services.parser.metadata_extractor import extract_decree_metadata
from app.services.parser.splitter import split_text_by_schools


def clean_json_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if not match:
        raise ValueError("JSON не найден")

    cleaned = match.group(0)
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)

    return cleaned


def parse_json_or_error(content: str) -> dict:
    cleaned = clean_json_text(content)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as e:
        pos = e.pos
        start = max(0, pos - 300)
        end = min(len(cleaned), pos + 300)
        raise ValueError(
            f"Ошибка JSON около позиции {pos}:\n\n{cleaned[start:end]}"
        )

    try:
        validated = DecreeResponseModel.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Ответ не соответствует схеме DecreeResponseModel:\n{e}")

    return validated.model_dump()


def parse_single_chunk(client, chunk: str) -> dict:
    prompt = DECREE_PARSE_PROMPT.replace("{text}", chunk[:4000])

    response = client.chat(prompt)
    content = response.choices[0].message.content

    return parse_json_or_error(content)


def merge_parsed_results(results: list[dict]) -> dict:
    final = {
        "decree": {
            "number": "",
            "date": "",
            "municipality": "",
        },
        "schools": [],
    }

    for item in results:
        decree = item.get("decree", {}) or {}

        if decree.get("number") and not final["decree"]["number"]:
            final["decree"]["number"] = decree.get("number")

        if decree.get("date") and not final["decree"]["date"]:
            final["decree"]["date"] = decree.get("date")

        if decree.get("municipality") and not final["decree"]["municipality"]:
            final["decree"]["municipality"] = decree.get("municipality")

        final["schools"].extend(item.get("schools", []) or [])

    return final


def parse_decree_with_gigachat(text: str) -> dict:
    client = get_gigachat_client()

    # 1. Дешёвые регэксповые метаданные. Используются как seed:
    #    LLM может уточнить, но если он промолчал — берём это.
    metadata = extract_decree_metadata(text)

    # 2. Чанк-парсинг через LLM
    chunks = split_text_by_schools(text)

    results: list[dict] = []
    errors: list[dict] = []

    for index, chunk in enumerate(chunks, start=1):
        try:
            parsed = parse_single_chunk(client, chunk)
            results.append(parsed)
        except Exception as e:
            errors.append({
                "chunk": index,
                "error": str(e),
                "preview": chunk[:500],
            })

    merged = merge_parsed_results(results)

    # 3. Заполняем метаданные из регэкспов там, где LLM не справился
    for key, value in metadata.items():
        if value and not merged["decree"].get(key):
            merged["decree"][key] = value

    if errors:
        merged["errors"] = errors

    return merged
