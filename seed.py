from app.db.session import Base, engine, SessionLocal
from app.models.models import Municipality, School, Decree, AddressRule


def seed():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        db.query(AddressRule).delete()
        db.query(Decree).delete()
        db.query(School).delete()
        db.query(Municipality).delete()

        municipality = Municipality(
            name="Березники",
            region="Пермский край"
        )
        db.add(municipality)
        db.flush()

        decree = Decree(
            municipality_id=municipality.id,
            number="01-02-252",
            date="06.03.2025",
            file_path="storage/decrees/06.03.2025-01-02-252.doc"
        )
        db.add(decree)
        db.flush()

        school_2 = School(
            municipality_id=municipality.id,
            name='МАОУ «Школа № 2 имени М. Горького»',
            address="г. Березники, ул. Пятилетки, д. 21"
        )
        db.add(school_2)
        db.flush()

        rules = [
            AddressRule(
                school_id=school_2.id,
                decree_id=decree.id,
                locality="Березники",
                street="Пятилетки",
                house_rule_raw="нечетные дома: 19-39",
                parity="odd",
                house_from=19,
                house_to=39,
            ),
            AddressRule(
                school_id=school_2.id,
                decree_id=decree.id,
                locality="Березники",
                street="Пятилетки",
                house_rule_raw="четные дома: 22-48",
                parity="even",
                house_from=22,
                house_to=48,
            ),
        ]

        db.add_all(rules)
        db.commit()

        print("База успешно заполнена тестовыми данными")

    finally:
        db.close()


if __name__ == "__main__":
    seed()