"""
Генерация PNG-схемы верхнеуровневой архитектуры сервиса (рисунок 3.1
общей части отчёта). На выходе — docs/img/architecture.png.

Схема:
    Браузер
       │
    FastAPI (уровень представления)
       │
    Доменные сервисы: parser · search · address · dadata · ai · ocr · validation
       │
    Внешние системы: SQLite · DaData · GigaChat · ocr.space
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT_PATH = Path(__file__).parent / "img" / "architecture.png"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# ───────────────────────── Параметры стиля ─────────────────────────

FONT_FAMILY = "DejaVu Sans"  # доступен в matplotlib по умолчанию
BOX_EDGE = "#1f3a5f"
BOX_FILL_PRES = "#dde7f3"     # уровень представления
BOX_FILL_DOMAIN = "#e8f1d8"   # доменные сервисы
BOX_FILL_EXT = "#f3e6cc"      # внешние системы
BOX_FILL_USER = "#f0f0f0"     # пользователь
ARROW_COLOR = "#1f3a5f"


def add_box(ax, x, y, w, h, text, fill, fontsize=11, bold=False):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.4, edgecolor=BOX_EDGE, facecolor=fill,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center",
        fontsize=fontsize, fontfamily=FONT_FAMILY,
        fontweight="bold" if bold else "normal",
        wrap=True,
    )
    return (x + w / 2, y, x + w / 2, y + h)  # центры низа и верха


def add_arrow(ax, x1, y1, x2, y2, label=None):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", mutation_scale=14,
        linewidth=1.2, color=ARROW_COLOR,
    )
    ax.add_patch(arrow)
    if label:
        ax.text(
            (x1 + x2) / 2 + 0.15, (y1 + y2) / 2, label,
            fontsize=9, fontfamily=FONT_FAMILY, color=ARROW_COLOR,
            ha="left", va="center", style="italic",
        )


# ───────────────────────── Холст ─────────────────────────

fig, ax = plt.subplots(figsize=(11, 7.5), dpi=200)
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.set_aspect("equal")
ax.axis("off")


# ───────────────────────── Уровень 1: пользователь ─────────────────────────

user_cx, user_bottom, _, user_top = add_box(
    ax, x=4.5, y=8.6, w=5, h=1.0,
    text="Браузер пользователя\n(родитель / администратор УО)",
    fill=BOX_FILL_USER, fontsize=11, bold=True,
)


# ───────────────────────── Уровень 2: FastAPI ─────────────────────────

pres_cx, pres_bottom, _, pres_top = add_box(
    ax, x=3.0, y=6.8, w=8, h=1.1,
    text="FastAPI · уровень представления\n(эндпоинты · шаблоны Jinja2 · формы)",
    fill=BOX_FILL_PRES, fontsize=11, bold=True,
)

add_arrow(ax, user_cx, user_bottom, pres_cx, pres_top, label="HTTP / HTML / JSON")


# ───────────────────────── Уровень 3: доменные сервисы ─────────────────────────

domain_x, domain_y, domain_w, domain_h = 0.6, 4.6, 12.8, 1.5
domain_box = FancyBboxPatch(
    (domain_x, domain_y), domain_w, domain_h,
    boxstyle="round,pad=0.02,rounding_size=0.15",
    linewidth=1.4, edgecolor=BOX_EDGE, facecolor=BOX_FILL_DOMAIN,
)
ax.add_patch(domain_box)
ax.text(
    domain_x + domain_w / 2, domain_y + domain_h - 0.32,
    "Доменные сервисы  (app/services/<domain>/)",
    ha="center", va="center", fontsize=11.5, fontweight="bold",
    fontfamily=FONT_FAMILY,
)

domain_labels = ["parser", "search", "address", "dadata", "ai", "ocr", "validation"]
n = len(domain_labels)
inner_y = domain_y + 0.35
inner_h = 0.55
gap = 0.18
inner_total = domain_w - 0.6
inner_w = (inner_total - gap * (n - 1)) / n
for i, label in enumerate(domain_labels):
    bx = domain_x + 0.3 + i * (inner_w + gap)
    sub = FancyBboxPatch(
        (bx, inner_y), inner_w, inner_h,
        boxstyle="round,pad=0.01,rounding_size=0.08",
        linewidth=1.0, edgecolor=BOX_EDGE, facecolor="white",
    )
    ax.add_patch(sub)
    ax.text(
        bx + inner_w / 2, inner_y + inner_h / 2, label,
        ha="center", va="center", fontsize=10.5, fontfamily=FONT_FAMILY,
    )

domain_top_cx = domain_x + domain_w / 2
domain_top_y = domain_y + domain_h
domain_bot_y = domain_y

add_arrow(ax, pres_cx, pres_bottom, domain_top_cx, domain_top_y)


# ───────────────────────── Уровень 4: внешние системы ─────────────────────────

ext_specs = [
    ("SQLite\n(БД)",     1.2),
    ("DaData\n(адреса)", 4.6),
    ("GigaChat\n(LLM)",  8.0),
    ("ocr.space\n(OCR)", 11.4),
]
ext_w, ext_h, ext_y = 1.9, 1.2, 1.6
for text, cx in ext_specs:
    bx = cx - ext_w / 2
    add_box(
        ax, x=bx, y=ext_y, w=ext_w, h=ext_h,
        text=text, fill=BOX_FILL_EXT, fontsize=10.5, bold=False,
    )
    # стрелка от низа доменного блока к верху внешнего
    add_arrow(ax, cx, domain_bot_y, cx, ext_y + ext_h)


# ───────────────────────── Легенда ─────────────────────────

legend_y = 0.55
legend_items = [
    ("Пользователь",       BOX_FILL_USER),
    ("Уровень представления", BOX_FILL_PRES),
    ("Доменные сервисы",   BOX_FILL_DOMAIN),
    ("Внешние системы",    BOX_FILL_EXT),
]
lx = 0.6
for text, color in legend_items:
    swatch = FancyBboxPatch(
        (lx, legend_y), 0.35, 0.35,
        boxstyle="round,pad=0.01,rounding_size=0.05",
        linewidth=1.0, edgecolor=BOX_EDGE, facecolor=color,
    )
    ax.add_patch(swatch)
    ax.text(
        lx + 0.45, legend_y + 0.17, text,
        ha="left", va="center", fontsize=9.5, fontfamily=FONT_FAMILY,
    )
    lx += 0.45 + len(text) * 0.13 + 0.6


# ───────────────────────── Сохранение ─────────────────────────

plt.tight_layout(pad=0.4)
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Готово: {OUT_PATH}")
