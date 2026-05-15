from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class Municipality(Base):
    __tablename__ = "municipalities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    region = Column(String, nullable=True)

    schools = relationship("School", back_populates="municipality")


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    municipality_id = Column(Integer, ForeignKey("municipalities.id"))

    name = Column(String, nullable=False)
    address = Column(String, nullable=True)

    municipality = relationship("Municipality", back_populates="schools")
    rules = relationship("AddressRule", back_populates="school")


class Decree(Base):
    __tablename__ = "decrees"

    id = Column(Integer, primary_key=True, index=True)
    municipality_id = Column(Integer, ForeignKey("municipalities.id"))

    number = Column(String, nullable=False)
    date = Column(String, nullable=False)
    file_path = Column(String, nullable=True)


class AddressRule(Base):
    __tablename__ = "address_rules"

    id = Column(Integer, primary_key=True, index=True)

    school_id = Column(Integer, ForeignKey("schools.id"))
    decree_id = Column(Integer, ForeignKey("decrees.id"))

    locality = Column(String, nullable=True)
    street = Column(String, nullable=False)
    normalized_street = Column(String, nullable=True)

    house_rule_raw = Column(String, nullable=False)

    rule_type = Column(String, default="unknown")
    parity = Column(String, default="all")

    house_from = Column(Integer, nullable=True)
    house_to = Column(Integer, nullable=True)
    house_number = Column(String, nullable=True)
    house_numbers = Column(String, nullable=True)
    exceptions = Column(String, nullable=True)

    comment = Column(String, nullable=True)

    dadata_value = Column(String, nullable=True)
    dadata_confidence = Column(String, nullable=True)
    validation_status = Column(String, default="unchecked")
    validation_comment = Column(String, nullable=True)

    school = relationship("School", back_populates="rules")
    decree = relationship("Decree")