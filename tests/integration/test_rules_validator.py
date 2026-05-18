"""Integration: валидатор правил находит пересечения и ошибки."""
from app.models.models import AddressRule, Decree, Municipality, School
from app.services.validation.rules_validator import validate_rules


def _setup_two_schools(db):
    """Создаёт 2 школы в одном муниципалитете с правилами."""
    muni = Municipality(name="Test")
    db.add(muni)
    db.flush()

    decree = Decree(municipality_id=muni.id, number="1", date="2025")
    db.add(decree)
    db.flush()

    s1 = School(municipality_id=muni.id, name="Школа 1")
    s2 = School(municipality_id=muni.id, name="Школа 2")
    db.add_all([s1, s2])
    db.flush()

    return muni, decree, s1, s2


def test_no_issues_for_disjoint_rules(db):
    _, decree, s1, s2 = _setup_two_schools(db)
    db.add(AddressRule(
        school_id=s1.id, decree_id=decree.id, street="Ленина",
        house_rule_raw="1-10", house_from=1, house_to=10, parity="all",
    ))
    db.add(AddressRule(
        school_id=s2.id, decree_id=decree.id, street="Ленина",
        house_rule_raw="11-20", house_from=11, house_to=20, parity="all",
    ))
    db.commit()

    issues = validate_rules(db)
    intersections = [i for i in issues if i["type"] == "intersection"]
    assert intersections == []


def test_detects_intersection(db):
    _, decree, s1, s2 = _setup_two_schools(db)
    db.add(AddressRule(
        school_id=s1.id, decree_id=decree.id, street="Ленина",
        house_rule_raw="1-10", house_from=1, house_to=10, parity="all",
    ))
    db.add(AddressRule(
        school_id=s2.id, decree_id=decree.id, street="Ленина",
        house_rule_raw="5-15", house_from=5, house_to=15, parity="all",
    ))
    db.commit()

    issues = validate_rules(db)
    intersections = [i for i in issues if i["type"] == "intersection"]
    assert len(intersections) >= 1


def test_detects_invalid_range(db):
    _, decree, s1, _ = _setup_two_schools(db)
    db.add(AddressRule(
        school_id=s1.id, decree_id=decree.id, street="Ленина",
        house_rule_raw="20-10", house_from=20, house_to=10, parity="all",
    ))
    db.commit()

    issues = validate_rules(db)
    invalid = [i for i in issues if i["type"] == "invalid_range"]
    assert len(invalid) == 1


def test_detects_empty_street(db):
    _, decree, s1, _ = _setup_two_schools(db)
    db.add(AddressRule(
        school_id=s1.id, decree_id=decree.id, street=" ",
        house_rule_raw="1-10", house_from=1, house_to=10, parity="all",
    ))
    db.commit()

    issues = validate_rules(db)
    empty = [i for i in issues if i["type"] == "empty_street"]
    assert len(empty) == 1
