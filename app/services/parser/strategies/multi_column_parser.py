"""
Парсер постановлений с многоколоночными таблицами:
    №  |  Школа  |  Улица  |  Дома

Если в файле такая таблица — извлекаем правила напрямую, БЕЗ обращения
к LLM (структура и так полная). Если файла нет / структура не
распознаётся — fallback на LLM-парсер `parse_decree_with_gigachat`.
"""
from pathlib import Path

from app.services.ai.gigachat.decree_parser import parse_decree_with_gigachat
from app.services.parser.metadata_extractor import extract_decree_metadata
from app.services.parser.multi_column_extractor import (
    extract_multi_column_rows_from_docx,
    extract_multi_column_rows_from_pdf,
    rows_to_decree_dict,
)
from app.services.parser.strategies.base import BaseParserStrategy
from app.services.parser.text_extractor import convert_doc_to_docx


def _extract_rows_for_file(file_path: str) -> list[dict]:
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        return extract_multi_column_rows_from_pdf(file_path)

    if suffix == ".docx":
        return extract_multi_column_rows_from_docx(file_path)

    if suffix == ".doc":
        converted = convert_doc_to_docx(file_path)
        if converted:
            return extract_multi_column_rows_from_docx(converted)
        return []

    return []


class MultiColumnParserStrategy(BaseParserStrategy):
    def parse(self, text: str, file_path: str | None = None) -> dict:
        metadata = extract_decree_metadata(text)

        if file_path:
            rows = _extract_rows_for_file(file_path)
            if rows:
                result = rows_to_decree_dict(rows, metadata)
                return result

        # Структурный экстрактор ничего не дал → LLM по тексту
        fallback = parse_decree_with_gigachat(text)

        # Если LLM не определил поля шапки — подкладываем регэкспы
        decree = fallback.get("decree", {}) or {}
        for key, value in metadata.items():
            if value and not decree.get(key):
                decree[key] = value
        fallback["decree"] = decree

        return fallback
