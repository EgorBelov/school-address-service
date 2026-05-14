import json
import re

from app.services.ai.gigachat.client import get_gigachat_client
from app.services.ai.gigachat.prompts import DECREE_PARSE_PROMPT
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
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        pos = e.pos
        start = max(0, pos - 300)
        end = min(len(cleaned), pos + 300)

        raise ValueError(
            f"Ошибка JSON около позиции {pos}:\n\n{cleaned[start:end]}"
        )


def parse_single_chunk(client, chunk: str, index: int) -> dict:
    prompt = DECREE_PARSE_PROMPT.replace("{text}", chunk[:4000])

    response = client.chat(prompt)
    content = response.choices[0].message.content

    parsed = parse_json_or_error(content)

    return parsed


def merge_parsed_results(results: list[dict]) -> dict:
    final = {
        "decree": {
            "number": "",
            "date": "",
            "municipality": ""
        },
        "schools": []
    }

    for item in results:
        decree = item.get("decree", {})

        if decree.get("number") and not final["decree"]["number"]:
            final["decree"]["number"] = decree.get("number")

        if decree.get("date") and not final["decree"]["date"]:
            final["decree"]["date"] = decree.get("date")

        if decree.get("municipality") and not final["decree"]["municipality"]:
            final["decree"]["municipality"] = decree.get("municipality")

        final["schools"].extend(item.get("schools", []))

    return final


def parse_decree_with_gigachat(text: str) -> dict:
    client = get_gigachat_client()

    chunks = split_text_by_schools(text)

    results = []
    errors = []

    for index, chunk in enumerate(chunks, start=1):
        try:
            parsed = parse_single_chunk(client, chunk, index)
            results.append(parsed)
        except Exception as e:
            errors.append({
                "chunk": index,
                "error": str(e),
                "preview": chunk[:500]
            })

    merged = merge_parsed_results(results)

    if errors:
        merged["errors"] = errors

    return merged