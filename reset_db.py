"""
Полная очистка БД и применение seed.py.
Используется, если данные в БД испорчены — например, школы попали
не в тот муниципалитет или появились дубликаты после нескольких
загрузок одного и того же постановления.

Запуск:
    python reset_db.py
"""
from app.db.session import Base, SessionLocal, engine
from app.models.models import AddressRule, Decree, Municipality, School
from seed import seed


def reset():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Порядок важен из-за FK
        deleted = {
            "address_rules": db.query(AddressRule).delete(),
            "decrees": db.query(Decree).delete(),
            "schools": db.query(School).delete(),
            "municipalities": db.query(Municipality).delete(),
        }
        db.commit()

        print("Удалено:")
        for table, count in deleted.items():
            print(f"  {table}: {count}")
    finally:
        db.close()

    print()
    print("Применяю seed.py…")
    seed()


if __name__ == "__main__":
    reset()
