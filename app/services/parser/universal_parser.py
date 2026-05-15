from app.services.ai.gigachat.classifier.document_classifier import classify_document
from app.services.parser.strategies.multi_column_parser import MultiColumnParserStrategy
from app.services.parser.strategies.two_column_parser import TwoColumnParserStrategy


def parse_document_universal(text: str, file_path: str | None = None) -> dict:
    classification = classify_document(text)

    document_type = classification.get("document_type")

    if document_type == "two_column_school_territories":
        parsed = TwoColumnParserStrategy().parse(text, file_path=file_path)

    elif document_type == "multi_column_street_house":
        parsed = MultiColumnParserStrategy().parse(text)

    else:
        parsed = MultiColumnParserStrategy().parse(text)

    parsed["classification"] = classification

    return parsed