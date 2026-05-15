import requests

from app.core.config import settings


OCR_SPACE_URL = "https://api.ocr.space/parse/image"


def extract_text_with_ocr_space(file_path: str) -> str:
    with open(file_path, "rb") as file:
        response = requests.post(
            OCR_SPACE_URL,
            headers={
                "apikey": settings.ocr_space_api_key,
            },
            files={
                "file": file,
            },
            data={
                "language": "rus",
                "isOverlayRequired": "false",
                "OCREngine": "2",
                "scale": "true",
                "detectOrientation": "true",
            },
            timeout=120,
        )

    response.raise_for_status()
    data = response.json()

    if data.get("IsErroredOnProcessing"):
        message = data.get("ErrorMessage") or data.get("ErrorDetails")
        raise RuntimeError(f"OCR.Space error: {message}")

    parsed_results = data.get("ParsedResults") or []

    texts = []

    for item in parsed_results:
        text = item.get("ParsedText")
        if text:
            texts.append(text)

    return "\n\n".join(texts).strip()