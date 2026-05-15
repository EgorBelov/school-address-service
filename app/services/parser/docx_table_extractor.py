"""
Извлечение строк «школа → территория» из .docx-таблиц.
Использует ту же логику process_table / stitch / dedup, что и
pdf_table_extractor — мы переиспользуем её для табличного DOCX.
"""
from docx import Document

from app.services.parser.pdf_table_extractor import (
    SCHOOL_NAME_RE,
    merge_duplicate_schools,
    process_table,
    stitch_split_names,
)


def _table_to_rows(table) -> list[list[str]]:
    """python-docx Table → list[list[str]] для process_table()."""
    raw: list[list[str]] = []
    for row in table.rows:
        raw.append([cell.text for cell in row.cells])
    return raw


def extract_school_table_rows_from_docx(file_path: str) -> list[dict]:
    doc = Document(file_path)

    rows: list[dict] = []

    for table_index, table in enumerate(doc.tables, start=1):
        raw_table = _table_to_rows(table)
        rows.extend(process_table(raw_table, page_index=table_index))

    rows = stitch_split_names(rows)
    rows = merge_duplicate_schools(rows)

    rows = [
        row for row in rows
        if len(row["territory_text"]) >= 10
        and (
            SCHOOL_NAME_RE.search(row["school_name"])
            or "учреждение" in row["school_name"].lower()
        )
    ]

    print(f"[docx_table_extractor] rows: {len(rows)}")

    return rows
