import json
import re
import time

from pydantic import ValidationError

from app.services.ai.gigachat.client import get_gigachat_client
from app.services.ai.gigachat.prompts import DECREE_PARSE_PROMPT
from app.services.ai.gigachat.schemas import DecreeResponseModel
from app.services.parser.metadata_extractor import extract_decree_metadata
from app.services.parser.splitter import split_text_by_schools


# Сколько секунд ждать между запросами к GigaChat (анти-throttle).
# Сбер бывает чувствителен к burst-нагрузке — лучше с запасом.
_INTER_REQUEST_DELAY = 2.5

# Retry при timeout / 429 / 5xx / SSL EOF
_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 4.0  # 4, 8, 16, 32 сек


def _is_transient_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in (
        # сеть/таймауты
        "timeout", "timed out",
        # rate limit и 5xx
        "429", "too many requests",
        "500", "502", "503", "504",
        # обрыв соединения
        "connection", "reset by peer", "disconnect",
        # SSL/TLS
        "ssl", "unexpected_eof", "handshake",
        "eof occurred", "protocol",
    ))


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


def parse_single_chunk_with_retry(client, chunk: str) -> dict:
    """Делаем до _MAX_RETRIES попыток на каждый чанк с backoff."""
    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return parse_single_chunk(client, chunk)
        except Exception as e:
            last_error = e

            if not _is_transient_error(e) or attempt == _MAX_RETRIES:
                raise

            wait = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            print(
                f"[gigachat] transient error on attempt {attempt}: {e}"
                f" → retry in {wait:.0f}s"
            )
            time.sleep(wait)

    # Недостижимо, но удовлетворим тайпчекер
    raise last_error if last_error else RuntimeError("unreachable")


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
        if index > 1:
            # Пауза между запросами, чтобы не упереться в 429
            time.sleep(_INTER_REQUEST_DELAY)

        try:
            parsed = parse_single_chunk_with_retry(client, chunk)
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
