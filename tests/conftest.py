"""
Общие фикстуры для тестов.

Главное:
  - `db_engine` — один in-memory SQLite (с `StaticPool`!) на тест.
    Без StaticPool каждая SQLAlchemy-сессия открывает СВОЮ in-memory БД,
    где нет таблиц — это самый частый pitfall с in-memory SQLite.
  - `db` — сессия SQLAlchemy.
  - `client` — FastAPI TestClient на той же in-memory БД.
  - DaData / GigaChat замоканы по умолчанию (autouse).
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_engine():
    """In-memory SQLite со StaticPool — все сессии видят одни и те же таблицы."""
    from app.db.session import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False)


@pytest.fixture
def db(db_session_factory):
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session_factory):
    """FastAPI TestClient, использующий тестовую in-memory БД."""
    from app.main import app, get_db

    def override_get_db():
        s = db_session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _disable_external_services():
    """
    По умолчанию НИЧЕГО реально не вызываем в DaData/GigaChat —
    отдельные тесты могут переопределить через свои патчи.
    """
    with patch(
        "app.services.dadata.client.suggest_address", return_value=[]
    ), patch(
        "app.services.dadata.client.clean_address", return_value=None
    ), patch(
        "app.services.dadata.street_validator._cached_suggest", return_value=tuple()
    ):
        yield
