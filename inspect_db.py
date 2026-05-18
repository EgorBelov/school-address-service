"""
Утилита для просмотра содержимого БД.

Применение:
    python inspect_db.py                  # сводка по муниципалитетам и школам
    python inspect_db.py Монастырская     # все правила, где улица содержит подстроку
    python inspect_db.py --school Флагман # правила одной школы
    python inspect_db.py --check "Пермь, Монастырская, 96"   # симуляция поиска
"""
import sys

from app.db.session import SessionLocal
from app.models.models import AddressRule, Municipality, School
from app.services.address.normalize import normalize_locality, normalize_street_name
from app.services.search.find_school import find_school_by_address


def summary(db):
    print("=== Муниципалитеты ===")
    for m in db.query(Municipality).order_by(Municipality.name).all():
        schools = (
            db.query(School).filter(School.municipality_id == m.id).count()
        )
        rules = (
            db.query(AddressRule)
            .join(School, AddressRule.school_id == School.id)
            .filter(School.municipality_id == m.id)
            .count()
        )
        print(f"  {m.id}: {m.name:40} schools={schools}  rules={rules}")

    total_schools = db.query(School).count()
    total_rules = db.query(AddressRule).count()
    print(f"\nИтого: {total_schools} школ, {total_rules} правил.")


def by_street(db, query):
    print(f"=== Правила со street содержащим {query!r} ===")
    target = normalize_street_name(query)
    found = 0
    for r in db.query(AddressRule).all():
        if target in normalize_street_name(r.street):
            muni = r.school.municipality.name if r.school and r.school.municipality else "—"
            print(f"  [{muni}] {r.school.name[:50] if r.school else '—'}")
            print(f"    street={r.street!r}  rule={r.house_rule_raw[:80]!r}")
            print(f"    parity={r.parity}  from={r.house_from}  to={r.house_to}")
            print(f"    house_number={r.house_number!r}  numbers={r.house_numbers!r}")
            found += 1
    if not found:
        print("  (ничего не найдено)")


def by_school(db, query):
    schools = db.query(School).all()
    matches = [s for s in schools if query.lower() in s.name.lower()]

    for s in matches:
        muni = s.municipality.name if s.municipality else "—"
        rules = db.query(AddressRule).filter(AddressRule.school_id == s.id).all()
        print(f"=== {s.name} ({muni}) — {len(rules)} правил ===")
        for r in rules:
            print(f"  {r.street:30} parity={r.parity:8} {r.house_from}-{r.house_to}  {r.house_rule_raw[:60]}")
        print()


def check_address(db, full):
    """full: "Пермь, Монастырская, 96" """
    parts = [p.strip() for p in full.split(",")]
    if len(parts) < 3:
        print("Используйте формат: 'Пермь, Монастырская, 96'")
        return
    locality, street, house = parts[0], parts[1], parts[2]
    print(f"locality={locality!r}  street={street!r}  house={house!r}")
    print(f"normalized: locality={normalize_locality(locality)!r}  street={normalize_street_name(street)!r}")
    m = find_school_by_address(db, locality=locality, street=street, house=house)
    if m:
        print(f"Найдено: {m['school'].name}  rule={m['rule'].house_rule_raw}")
    else:
        print("Не найдено")


def main():
    db = SessionLocal()
    try:
        if len(sys.argv) < 2:
            summary(db)
        elif sys.argv[1] == "--school":
            by_school(db, " ".join(sys.argv[2:]))
        elif sys.argv[1] == "--check":
            check_address(db, " ".join(sys.argv[2:]))
        else:
            by_street(db, sys.argv[1])
    finally:
        db.close()


if __name__ == "__main__":
    main()
