from fastapi import FastAPI, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import Base, engine, SessionLocal
from app.models import models
from app.services.search.find_school import find_school_by_address
from fastapi.responses import JSONResponse
from app.services.dadata.client import clean_address, suggest_address
from pathlib import Path
from fastapi import UploadFile, File
from app.services.parser.text_extractor import extract_text
import json
from app.services.ai.gigachat.decree_parser import parse_decree_with_gigachat
from app.services.parser.save_parsed_decree import save_parsed_decree
from app.models.models import AddressRule, School, Decree
from app.services.validation.rules_validator import validate_rules


Base.metadata.create_all(bind=engine)

app = FastAPI(title="School Address Service")

templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"result": None, "error": None}
    )


@app.post("/search", response_class=HTMLResponse)
def search(
    request: Request,
    address: str = Form(...),
    db: Session = Depends(get_db)
):
    normalized = clean_address(address)

    if not normalized:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "result": None,
                "error": "DaData не настроена или адрес не удалось проверить."
            }
        )

    city = normalized.get("city") or normalized.get("settlement")
    street = normalized.get("street")
    house = normalized.get("house")

    if not street or not house:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "result": None,
                "error": "Адрес распознан не полностью. Укажите улицу и дом."
            }
        )

    match = find_school_by_address(
        db=db,
        locality=city,
        street=street,
        house=house
    )

    if not match:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "result": None,
                "error": f"Школа для адреса {normalized.get('result')} не найдена."
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": {
                "address": normalized.get("result"),
                "school_name": match["school"].name,
                "school_address": match["school"].address,
                "rule": match["rule"].house_rule_raw,
                "street": match["rule"].street,
                "decree_number": match["rule"].decree.number if match["rule"].decree else "—",
                "decree_date": match["rule"].decree.date if match["rule"].decree else "—",
            },
            "error": None
        }
    )

@app.get("/api/address/suggest")
def api_address_suggest(q: str):
    suggestions = suggest_address(q)

    return JSONResponse([
        {
            "value": item.get("value"),
            "unrestricted_value": item.get("unrestricted_value"),
            "data": {
                "city": item.get("data", {}).get("city") or item.get("data", {}).get("settlement"),
                "street": item.get("data", {}).get("street"),
                "house": item.get("data", {}).get("house"),
            }
        }
        for item in suggestions
    ])

@app.get("/admin/upload", response_class=HTMLResponse)
def admin_upload_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin_upload.html",
        context={"text": None, "error": None}
    )


@app.post("/admin/upload", response_class=HTMLResponse)
def admin_upload_file(
    request: Request,
    file: UploadFile = File(...)
):
    try:
        upload_dir = Path("storage/decrees")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename

        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())

        extracted_text = extract_text(str(file_path))

        extracted_dir = Path("storage/extracted")
        extracted_dir.mkdir(parents=True, exist_ok=True)

        text_path = extracted_dir / f"{file.filename}.txt"
        text_path.write_text(extracted_text, encoding="utf-8")

        return templates.TemplateResponse(
            request=request,
            name="admin_upload.html",
            context={
                "text": extracted_text[:8000],
                "error": None
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="admin_upload.html",
            context={
                "text": None,
                "error": str(e)
            }
        )
    
@app.post("/admin/parse-with-ai", response_class=HTMLResponse)
def admin_parse_with_ai(
    request: Request,
    text: str = Form(...)
):
    try:
        parsed = parse_decree_with_gigachat(text)

        return templates.TemplateResponse(
            request=request,
            name="admin_upload.html",
            context={
                "text": text,
                "parsed": json.dumps(parsed, ensure_ascii=False, indent=2),
                "error": None
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="admin_upload.html",
            context={
                "text": text,
                "parsed": None,
                "error": f"Ошибка AI-парсинга: {e}"
            }
        )
    
@app.post("/admin/save-parsed", response_class=HTMLResponse)
def admin_save_parsed(
    request: Request,
    parsed_json: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        parsed = json.loads(parsed_json)
        saved = save_parsed_decree(db, parsed)

        return templates.TemplateResponse(
            request=request,
            name="admin_upload.html",
            context={
                "text": None,
                "parsed": json.dumps(parsed, ensure_ascii=False, indent=2),
                "saved": saved,
                "error": None
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="admin_upload.html",
            context={
                "text": None,
                "parsed": parsed_json,
                "saved": None,
                "error": f"Ошибка сохранения в БД: {e}"
            }
        )

@app.get("/admin/rules", response_class=HTMLResponse)
def admin_rules_page(
    request: Request,
    db: Session = Depends(get_db)
):
    rules = (
        db.query(AddressRule)
        .join(School, AddressRule.school_id == School.id)
        .join(Decree, AddressRule.decree_id == Decree.id)
        .order_by(School.name, AddressRule.street)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin_rules.html",
        context={"rules": rules}
    )

@app.get("/admin/validation", response_class=HTMLResponse)
def admin_validation_page(
    request: Request,
    db: Session = Depends(get_db)
):
    issues = validate_rules(db)

    return templates.TemplateResponse(
        request=request,
        name="admin_validation.html",
        context={"issues": issues}
    )

@app.post("/admin/rules/delete/{rule_id}")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    rule = db.query(AddressRule).filter(AddressRule.id == rule_id).first()

    if rule:
        db.delete(rule)
        db.commit()

    return RedirectResponse(
        url="/admin/rules",
        status_code=303
    )

@app.post("/admin/rules/update/{rule_id}")
def update_rule(
    rule_id: int,
    street: str = Form(...),
    house_rule_raw: str = Form(...),
    parity: str = Form(...),
    house_from: str = Form(""),
    house_to: str = Form(""),
    house_number: str = Form(""),
    db: Session = Depends(get_db)
):
    rule = db.query(AddressRule).filter(AddressRule.id == rule_id).first()

    if rule:
        rule.street = street.strip()
        rule.house_rule_raw = house_rule_raw.strip()
        rule.parity = parity.strip()
        rule.house_from = int(house_from) if house_from.strip().isdigit() else None
        rule.house_to = int(house_to) if house_to.strip().isdigit() else None
        rule.house_number = house_number.strip() or None

        db.commit()

    return RedirectResponse(
        url="/admin/rules",
        status_code=303
    )