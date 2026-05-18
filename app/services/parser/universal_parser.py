"""
Диспетчер парсеров.

Алгоритм:
1. Если файл есть — пробуем структурно определить формат таблицы:
     a) Многоколоночная (№ | Школа | Улица | Дома)  → MultiColumnParserStrategy
     b) Двухколоночная (Школа | Территория)         → TwoColumnParserStrategy
   Это бесплатно (без LLM), и гораздо надёжнее, чем спрашивать у LLM
   «какой это тип документа».
2. Если структуру определить не удалось — спрашиваем LLM-классификатор
   и идём по его подсказке.
3. Если и LLM-классификатор молчит — fallback на multi_column (внутри
   которой ещё один fallback на чисто LLM-парсинг сырого текста).
"""
from pathlib import Path

from app.services.ai.gigachat.classifier.document_classifier import classify_document
from app.services.parser.multi_column_extractor import is_multi_column_format
from app.services.parser.strategies.multi_column_parser import MultiColumnParserStrategy
from app.services.parser.strategies.two_column_parser import TwoColumnParserStrategy


def _two_column_header_looks_right(cells_header: list) -> bool:
    """Шапка двухколоночной таблицы «Школа | Территории/Улицы»."""
    text = " ".join(str(c or "") for c in cells_header).lower()
    if "наименование" not in text:
        return False
    return any(marker in text for marker in (
        "территор", "улиц", "адрес", "закрепл",
    ))


def _is_two_column_format(file_path: str) -> bool:
    """Эвристика для двухколоночных таблиц «Школа | Территория»."""
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages[:10]:
                    for table in page.extract_tables() or []:
                        if not table or not table[0]:
                            continue
                        if len(table[0]) == 2 and _two_column_header_looks_right(table[0]):
                            return True
        except Exception:
            return False

    if suffix == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            for table in doc.tables[:10]:
                if not table.rows:
                    continue
                cells = [c.text for c in table.rows[0].cells]
                if len(cells) == 2 and _two_column_header_looks_right(cells):
                    return True
        except Exception:
            return False

    return False


def parse_document_universal(text: str, file_path: str | None = None) -> dict:
    classification: dict = {}

    print(f"[universal_parser] start: file_path={file_path!r}")

    # 1. Структурная авто-детекция (без LLM)
    if file_path:
        if is_multi_column_format(file_path):
            print(f"[universal_parser] structural detect: MULTI_COLUMN → MultiColumnParserStrategy")
            classification = {
                "document_type": "multi_column_street_house",
                "confidence": 1.0,
                "reason": "structural: table with 4+ columns (Школа | Улица | Дома)",
            }
            parsed = MultiColumnParserStrategy().parse(text, file_path=file_path)
            parsed["classification"] = classification
            return parsed

        if _is_two_column_format(file_path):
            print(f"[universal_parser] structural detect: TWO_COLUMN → TwoColumnParserStrategy")
            classification = {
                "document_type": "two_column_school_territories",
                "confidence": 1.0,
                "reason": "structural: table with 2 columns (Школа | Территория)",
            }
            parsed = TwoColumnParserStrategy().parse(text, file_path=file_path)
            parsed["classification"] = classification
            return parsed

        print(f"[universal_parser] structural detect: not recognised → ask LLM")

    # 2. Структурно не распознали — спрашиваем LLM-классификатор
    try:
        classification = classify_document(text)
    except Exception as e:
        classification = {"document_type": "unknown", "reason": str(e)}

    document_type = classification.get("document_type")
    print(f"[universal_parser] LLM classification: {document_type}")

    if document_type == "two_column_school_territories":
        parsed = TwoColumnParserStrategy().parse(text, file_path=file_path)
    elif document_type == "multi_column_street_house":
        parsed = MultiColumnParserStrategy().parse(text, file_path=file_path)
    else:
        # Универсальный fallback (внутри сам решит: структурный или LLM)
        parsed = MultiColumnParserStrategy().parse(text, file_path=file_path)

    parsed["classification"] = classification
    return parsed
