"""Integration: сохранение распарсенного постановления + поиск по нему."""
from app.services.parser.save_parsed_decree import save_parsed_decree
from app.services.search.find_school import find_school_by_address


SAMPLE_PARSED = {
    "decree": {"number": "01-02-252", "date": "06.03.2025", "municipality": "Берёзники"},
    "schools": [
        {
            "name": "МАОУ «Школа № 2 имени М. Горького»",
            "address": "ул. Пятилетки, д. 21",
            "rules": [
                {
                    "locality": "Берёзники",
                    "street": "Пятилетки",
                    "house_rule_raw": "нечетные дома: 19-39",
                    "parity": "odd",
                    "house_from": 19,
                    "house_to": 39,
                    "rule_type": "range",
                },
                {
                    "locality": "Берёзники",
                    "street": "Пятилетки",
                    "house_rule_raw": "четные дома: 22-48",
                    "parity": "even",
                    "house_from": 22,
                    "house_to": 48,
                    "rule_type": "range",
                },
            ],
        }
    ],
}


def test_save_creates_municipality_school_rules(db):
    """Один вызов save_parsed_decree должен создать все нужные сущности."""
    from app.models.models import AddressRule, Decree, Municipality, School

    result = save_parsed_decree(db, SAMPLE_PARSED)

    assert result["schools_count"] == 1
    assert result["rules_count"] == 2
    assert result["municipality"] == "Берёзники"

    assert db.query(Municipality).count() == 1
    assert db.query(School).count() == 1
    assert db.query(Decree).count() == 1
    assert db.query(AddressRule).count() == 2


def test_save_then_search_finds_school(db):
    """После сохранения адрес из правила должен находиться."""
    save_parsed_decree(db, SAMPLE_PARSED)

    # Чётный дом 22 → second rule
    m = find_school_by_address(
        db, locality="г Берёзники", street="ул Пятилетки", house="22"
    )
    assert m is not None
    assert "Горького" in m["school"].name
    assert m["rule"].parity == "even"


def test_search_respects_locality(db):
    """Адрес в другом городе не должен матчиться с правилами Берёзников."""
    save_parsed_decree(db, SAMPLE_PARSED)

    m = find_school_by_address(
        db, locality="г Балашиха", street="Пятилетки", house="22"
    )
    assert m is None


def test_search_respects_parity(db):
    """Нечётный дом не должен попасть в правило для чётных."""
    save_parsed_decree(db, SAMPLE_PARSED)

    # 23 — нечётный, попадает в первое правило (odd 19-39)
    m = find_school_by_address(db, "Берёзники", "Пятилетки", "23")
    assert m is not None
    assert m["rule"].parity == "odd"

    # 50 — за пределами обоих диапазонов
    m = find_school_by_address(db, "Берёзники", "Пятилетки", "50")
    assert m is None


def test_search_missing_address_returns_none(db):
    save_parsed_decree(db, SAMPLE_PARSED)
    m = find_school_by_address(db, "Берёзники", "НесуществующаяУлица", "1")
    assert m is None


def test_save_idempotent_for_same_school(db):
    """Повторное сохранение тех же школ → не дублируем."""
    from app.models.models import School

    save_parsed_decree(db, SAMPLE_PARSED)
    save_parsed_decree(db, SAMPLE_PARSED)
    # Та же школа должна быть одна (find или create по имени+муниципалитету)
    assert db.query(School).count() == 1


def test_save_sanitizes_garbage_address(db):
    """LLM-мусор в address не должен записаться."""
    from app.models.models import School

    parsed = {
        "decree": {"municipality": "Test"},
        "schools": [{
            "name": "Школа X",
            "address": "ул. Объединения, 4, 6",  # это территория, не адрес
            "rules": [{"street": "Y", "house_rule_raw": "1"}],
        }],
    }
    save_parsed_decree(db, parsed)
    school = db.query(School).filter(School.name == "Школа X").first()
    assert school is not None
    assert school.address is None
