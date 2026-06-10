"""
Общая инфраструктура для генерации отчётов (общая часть + 6 индивидуальных).
Стили, шрифт, шапка титульной страницы.
"""
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt


FONT = "Times New Roman"
FONT_SIZE = 14
LINE_SPACING = 1.5


def _set_font(run, size=FONT_SIZE, bold=False, italic=False):
    run.font.name = FONT
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(attr), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def _paragraph_format(p, first_line_indent=1.25, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                     space_after=0, space_before=0):
    pf = p.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.alignment = align
    if first_line_indent:
        pf.first_line_indent = Cm(first_line_indent)


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    pf.space_before = Pt(18 if level == 1 else 12)
    pf.space_after = Pt(12 if level == 1 else 6)
    pf.first_line_indent = Cm(0)

    run = p.add_run(text)
    _set_font(run, size=FONT_SIZE + (2 if level == 1 else 0), bold=True)
    return p


def add_para(doc, text, bold=False, italic=False, first_line_indent=1.25,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    _paragraph_format(p, first_line_indent=first_line_indent, align=align)
    run = p.add_run(text)
    _set_font(run, bold=bold, italic=italic)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    pf = p.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.space_after = Pt(0)
    pf.first_line_indent = Cm(0)
    pf.left_indent = Cm(1.0)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    _set_font(run)
    return p


def add_table_simple(doc, rows, header=True, col_widths=None):
    """Простая таблица. rows[0] — шапка."""
    n_cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=n_cols)
    table.style = "Table Grid"
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for i, row in enumerate(rows):
        for j, cell_text in enumerate(row):
            cell = table.cell(i, j)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.first_line_indent = Cm(0)
            run = p.add_run(cell_text)
            _set_font(run, size=12, bold=(header and i == 0))

    if col_widths:
        for j, width in enumerate(col_widths):
            for row in table.rows:
                row.cells[j].width = Cm(width)
    return table


def add_note(doc, text):
    """Курсивный блок-инструкция для шаблонов индивидуальных отчётов:
    «здесь нужно описать то-то и то-то»."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.space_after = Pt(6)
    pf.space_before = Pt(2)
    pf.first_line_indent = Cm(0)
    pf.left_indent = Cm(0.5)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run("📝 ")
    _set_font(run, bold=True, italic=True)
    run2 = p.add_run(text)
    _set_font(run2, italic=True)
    return p


def new_document():
    """Создаёт Document с правильными полями и базовым стилем."""
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(3)
        section.right_margin = Cm(1.5)

    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(FONT_SIZE)
    rPr = style.element.get_or_add_rPr()
    rFonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(attr), FONT)
    rPr.append(rFonts)
    return doc


def add_title_page(doc, part_subtitle, author_placeholder="________________________"):
    """Стандартный титул. part_subtitle — пояснение, что это за часть отчёта
    (например, «Общая часть» или «Индивидуальная часть. Руководитель проекта»)."""
    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = LINE_SPACING
    run = p.add_run(
        "Пермский филиал федерального государственного автономного "
        "образовательного учреждения высшего образования\n"
        "«Национальный исследовательский университет\n"
        "«Высшая школа экономики»"
    )
    _set_font(run)

    for _ in range(2):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Факультет социально-экономических и компьютерных наук")
    _set_font(run)

    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("РАЗРАБОТКА ВЕБ-СЕРВИСА ОПРЕДЕЛЕНИЯ ШКОЛЫ "
                    "ПО АДРЕСУ ПРОЖИВАНИЯ НА ОСНОВЕ "
                    "МУНИЦИПАЛЬНЫХ ПОСТАНОВЛЕНИЙ")
    _set_font(run, bold=True)

    for _ in range(2):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Отчёт о групповом проекте")
    _set_font(run, italic=True)

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(part_subtitle)
    _set_font(run, italic=True, bold=True)

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(
        "образовательной программы «Программная инженерия»\n"
        "по направлению подготовки 09.03.04 Программная инженерия"
    )
    _set_font(run)

    for _ in range(4):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(f"Выполнил: {author_placeholder}")
    _set_font(run)

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(f"Руководитель: {author_placeholder}")
    _set_font(run)

    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Пермь, 2026 год")
    _set_font(run)

    doc.add_page_break()
