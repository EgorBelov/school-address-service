from pathlib import Path
import subprocess

import pdfplumber
import pytesseract
from docx import Document
from pdf2image import convert_from_path


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    lines = []

    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            lines.append(paragraph.text.strip())

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))

    return "\n".join(lines)


def extract_text_from_pdf_native(file_path: str) -> str:
    lines = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                lines.append(text)

    return "\n\n".join(lines)


def extract_text_from_pdf_ocr(file_path: str) -> str:
    pages = convert_from_path(file_path, dpi=300)
    result = []

    for index, page in enumerate(pages, start=1):
        text = pytesseract.image_to_string(
            page,
            lang="rus+eng"
        )

        result.append(f"\n--- OCR PAGE {index} ---\n{text}")

    return "\n\n".join(result)


def extract_text_from_pdf(file_path: str) -> str:
    native_text = extract_text_from_pdf_native(file_path)

    # Если текста мало — считаем, что это скан
    if len(native_text.strip()) >= 500:
        return native_text

    return extract_text_from_pdf_ocr(file_path)


def extract_text_from_doc(file_path: str) -> str:
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", file_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def extract_text(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()

    if suffix == ".docx":
        return extract_text_from_docx(file_path)

    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)

    if suffix == ".doc":
        return extract_text_from_doc(file_path)

    raise ValueError(f"Неподдерживаемый формат файла: {suffix}")